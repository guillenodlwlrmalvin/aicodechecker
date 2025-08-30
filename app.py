import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash

from models import initialize_database, get_user_by_username, create_user, create_analysis, get_recent_analyses
from detector import analyze_code
from code_check import check_code, validate_language_match
from lm_client import classify_with_lmstudio, detect_language_with_lmstudio


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    app.config['DATABASE'] = os.path.join(app.root_path, 'database.sqlite3')

    # Ensure database exists
    with app.app_context():
        initialize_database(app.config['DATABASE'])

    @app.before_request
    def load_logged_in_user():
        username = session.get('username')
        g.user = None
        if username:
            g.user = get_user_by_username(app.config['DATABASE'], username)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm', '')

            if not username or not password:
                flash('Username and password are required.', 'error')
                return render_template('register.html')

            if password != confirm:
                flash('Passwords do not match.', 'error')
                return render_template('register.html')

            if get_user_by_username(app.config['DATABASE'], username):
                flash('Username is already taken.', 'error')
                return render_template('register.html')

            password_hash = generate_password_hash(password)
            create_user(app.config['DATABASE'], username, password_hash)
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            user = get_user_by_username(app.config['DATABASE'], username)
            if user and check_password_hash(user['password_hash'], password):
                session['username'] = user['username']
                flash('Logged in successfully.', 'success')
                return redirect(url_for('dashboard'))

            flash('Invalid username or password.', 'error')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    @app.route('/dashboard', methods=['GET'])
    def dashboard():
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
        return render_template('dashboard.html', history=history)

    @app.route('/detect', methods=['POST'])
    def detect():
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))

        code = request.form.get('code', '')
        language = request.form.get('language', 'auto')
        if not code.strip():
            flash('Please paste some code.', 'error')
            return redirect(url_for('dashboard'))
        
        # Validate that the code matches the selected language
        if language and language.lower() != 'auto':
            is_valid, error_message = validate_language_match(code, language)
            if not is_valid:
                flash(f'Language mismatch: {error_message}', 'error')
                return redirect(url_for('dashboard'))

        # AI-powered language detection (fallback to heuristic)
        detected_language = None
        detected_source = 'heuristic'
        lm_lang = detect_language_with_lmstudio(code)
        if lm_lang and lm_lang not in ('', 'unknown'):
            detected_language = lm_lang
            detected_source = 'llm'
        else:
            check = check_code(code, language)
            detected_language = check.get('language') or 'unknown'

        if (not language) or (language.strip().lower() in ('auto', 'detect', 'auto-detect')):
            language = detected_language

        heuristic = analyze_code(code, language)
        llm_result = classify_with_lmstudio(code, language)

        # Build feedback preferring LLM
        feedback = None
        try:
            if llm_result and llm_result.get('label') and 'Unavailable' not in llm_result['label']:
                score = float(llm_result.get('score', 50.0))
                if 'AI' in llm_result['label'].upper():
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai' }
                elif 'HUMAN' in llm_result['label'].upper():
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain' }
            else:
                score = float(heuristic.get('score', 50.0))
                if 'AI' in heuristic.get('label', '').upper():
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai' }
                elif 'HUMAN' in heuristic.get('label', '').upper():
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain' }
        except Exception:
            feedback = None

        # Record analysis
        try:
            # Use heuristic for stored score/label to keep storage consistent
            check_for_store = check_code(code, language)
            create_analysis(
                app.config['DATABASE'],
                g.user['id'],
                code,
                language,
                heuristic_label=heuristic['label'],
                heuristic_score=float(heuristic['score']),
                check_ok=bool(check_for_store['ok']),
                check_errors=list(check_for_store.get('errors') or []),
            )
        except Exception as e:
            app.logger.warning(f"Failed to record analysis: {e}")

        history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)

        return render_template(
            'dashboard.html',
            result=heuristic,
            llm_result=llm_result,
            feedback=feedback,
            code_input=code,
            language=language,
            detected_language=detected_language,
            detected_source=detected_source,
            history=history,
        )

    @app.route('/clear_history', methods=['POST'])
    def clear_history():
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        
        try:
            # Clear all analyses for the current user
            conn = sqlite3.connect(app.config['DATABASE'])
            cursor = conn.cursor()
            cursor.execute('DELETE FROM analyses WHERE user_id = ?', (g.user['id'],))
            conn.commit()
            conn.close()
            
            flash('Analysis history has been cleared.', 'success')
        except Exception as e:
            app.logger.error(f"Failed to clear history: {e}")
            flash('Failed to clear history. Please try again.', 'error')
        
        return redirect(url_for('dashboard'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True) 
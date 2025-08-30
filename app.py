import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from models import initialize_database, get_user_by_username, create_user, create_analysis, get_recent_analyses, create_uploaded_file, get_uploaded_files
from detector import analyze_code
from code_check import check_code, validate_language_match
from lm_client import classify_with_lmstudio, detect_language_with_lmstudio
from deep_learning_detector import analyze_code_deep_learning

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['DATABASE'] = 'database.sqlite3'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'py': 'python',
    'java': 'java', 
    'cs': 'csharp',
    'cpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'c': 'cpp',
    'js': 'javascript',
    'ts': 'typescript',
    'php': 'php',
    'rb': 'ruby',
    'go': 'go',
    'rs': 'rust',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'r': 'r',
    'm': 'matlab'
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_language_from_extension(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return ALLOWED_EXTENSIONS.get(ext, 'auto')

# Initialize database
initialize_database(app.config['DATABASE'])

@app.before_request
def load_logged_in_user():
    g.user = None
    if 'user_id' in session:
        g.user = get_user_by_username(app.config['DATABASE'], session['user_id'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('Please fill in all fields.', 'error')
        else:
            try:
                create_user(app.config['DATABASE'], username, generate_password_hash(password))
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                flash(f'Registration failed: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user_by_username(app.config['DATABASE'], username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
    uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
    return render_template('dashboard.html', history=history, uploaded_files=uploaded_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('dashboard'))
    
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('dashboard'))
    
    if file and allowed_file(file.filename):
        try:
            # Read file content
            content = file.read().decode('utf-8')
            file_size = len(content.encode('utf-8'))
            
            # Generate secure filename
            filename = secure_filename(file.filename)
            
            # Get file type and suggested language
            file_type = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            suggested_language = get_language_from_extension(filename)
            
            # Store file in database
            file_id = create_uploaded_file(
                app.config['DATABASE'],
                g.user['id'],
                filename,
                file.filename,  # original filename
                file_size,
                file_type,
                content
            )
            
            flash(f'File "{file.filename}" uploaded successfully! You can now load it for analysis.', 'success')
            
            # Redirect back to dashboard with upload success parameter
            return redirect(url_for('dashboard', upload='success'))
            
        except Exception as e:
            flash(f'Error uploading file: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
    else:
        flash('File type not allowed. Please upload a code file.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/detect', methods=['POST'])
def detect():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        code = request.form.get('code', '').strip()
        file_id = request.form.get('file_id')
        
        if not code:
            flash('Please paste some code.', 'error')
            return redirect(url_for('dashboard'))
        
        # AI-powered language detection (fallback to heuristic)
        detected_language = None
        detected_source = 'heuristic'
        lm_lang = detect_language_with_lmstudio(code)
        if lm_lang and lm_lang not in ('', 'unknown'):
            detected_language = lm_lang
            detected_source = 'llm'
        else:
            check = check_code(code, 'auto')
            detected_language = check.get('language') or 'unknown'

        # Always use detected language
        language = detected_language

        heuristic = analyze_code(code, language)
        llm_result = classify_with_lmstudio(code, language)
        
        # Deep Learning Analysis
        deep_learning_result = analyze_code_deep_learning(code, language)
        
        # Build feedback with priority: Deep Learning > LLM > Heuristic
        feedback = None
        try:
            # Try Deep Learning first (most accurate)
            if deep_learning_result and deep_learning_result.get('score') is not None:
                score = deep_learning_result['score']
                if score > 75:
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai', 'source': 'Deep Learning' }
                elif score < 25:
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human', 'source': 'Deep Learning' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain', 'source': 'Deep Learning' }
            
            # Fallback to LLM if Deep Learning fails
            elif llm_result and llm_result.get('label') and 'Unavailable' not in llm_result['label']:
                score = float(llm_result.get('score', 50.0))
                if 'AI' in llm_result['label'].upper():
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai', 'source': 'AI Model' }
                elif 'HUMAN' in llm_result['label'].upper():
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human', 'source': 'AI Model' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain', 'source': 'AI Model' }
            
            # Final fallback to heuristic
            else:
                score = float(heuristic.get('score', 50.0))
                if 'AI' in heuristic.get('label', '').upper():
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai', 'source': 'Heuristic' }
                elif 'HUMAN' in heuristic.get('label', '').upper():
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human', 'source': 'Heuristic' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain', 'source': 'Heuristic' }
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
                file_id=int(file_id) if file_id else None,
            )
        except Exception as e:
            app.logger.warning(f"Failed to record analysis: {e}")

        history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
        uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)

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
            uploaded_files=uploaded_files,
        )
                             
    except Exception as e:
        app.logger.error(f"Code analysis failed: {e}")
        flash('An error occurred during analysis. Please try again.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/clear_history', methods=['POST'])
def clear_history():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        conn.execute("DELETE FROM analyses WHERE user_id = ?", (g.user['id'],))
        conn.commit()
        conn.close()
        flash('Analysis history cleared successfully!', 'success')
    except Exception as e:
        flash(f'Error clearing history: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/clear_uploaded_files', methods=['POST'])
def clear_uploaded_files():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        # First, remove file_id references from analyses
        conn.execute("UPDATE analyses SET file_id = NULL WHERE user_id = ?", (g.user['id'],))
        # Then delete all uploaded files
        conn.execute("DELETE FROM uploaded_files WHERE user_id = ?", (g.user['id'],))
        conn.commit()
        conn.close()
        flash('All uploaded files cleared successfully!', 'success')
    except Exception as e:
        flash(f'Error clearing uploaded files: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/remove_uploaded_file/<int:file_id>', methods=['POST'])
def remove_uploaded_file(file_id):
    if not g.user:
        return jsonify({'success': False, 'message': 'Please log in to continue.'}), 401
    
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        # First, remove file_id references from analyses
        conn.execute("UPDATE analyses SET file_id = NULL WHERE user_id = ? AND file_id = ?", (g.user['id'], file_id))
        # Then delete the specific uploaded file
        conn.execute("DELETE FROM uploaded_files WHERE id = ? AND user_id = ?", (file_id, g.user['id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'File removed successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error removing file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True) 
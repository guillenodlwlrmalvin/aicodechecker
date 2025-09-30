import os
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from models import initialize_database, get_user_by_username, create_user, create_analysis, get_recent_analyses, create_uploaded_file, get_uploaded_files
from models import list_all_users, delete_user_and_related, get_user_count
from models import approve_user, get_user_by_id
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
# Known languages vocabulary for normalizing LLM outputs
KNOWN_LANGUAGES = set(ALLOWED_EXTENSIONS.values())


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_language_from_extension(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return ALLOWED_EXTENSIONS.get(ext, 'auto')


# Initialize database
initialize_database(app.config['DATABASE'])

# Seed or fix default admin account (approved)
try:
    _existing_admin = get_user_by_username(app.config['DATABASE'], 'Admin')
    if not _existing_admin:
        create_user(app.config['DATABASE'], 'Admin', generate_password_hash('Admin123'), is_admin=True, is_approved=True)
    else:
        # Ensure Admin account is approved, has admin role, and known password
        conn = sqlite3.connect(app.config['DATABASE'])
        conn.execute(
            "UPDATE users SET is_admin = 1, is_approved = 1, password_hash = ? WHERE username = 'Admin'",
            (generate_password_hash('Admin123'),)
        )
        conn.commit()
        conn.close()
except Exception:
    pass

@app.before_request
def load_logged_in_user():
    g.user = None
    if 'user_id' in session:
        g.user = get_user_by_username(app.config['DATABASE'], session['user_id'])

# Admin utilities
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if not g.user.get('is_admin'):
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return view_func(*args, **kwargs)
    return wrapped

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
                # First user becomes admin automatically and approved
                is_first_user = get_user_count(app.config['DATABASE']) == 0
                create_user(
                    app.config['DATABASE'],
                    username,
                    generate_password_hash(password),
                    is_admin=is_first_user,
                    is_approved=is_first_user,
                )
                if is_first_user:
                    flash('Registration successful! Your account has admin privileges and is approved.', 'success')
                else:
                    flash('Registration successful! Awaiting admin approval.', 'info')
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
            if not user.get('is_approved'):
                flash('Your account is pending approval by an admin.', 'warning')
                return redirect(url_for('login'))
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

# Admin routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    users = list_all_users(app.config['DATABASE'])
    return render_template('admin.html', users=users)

@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_approve_user(user_id: int):
    try:
        approve_user(app.config['DATABASE'], user_id)
        flash('User approved successfully.', 'success')
    except Exception as e:
        flash(f'Failed to approve user: {str(e)}', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id: int):
    if g.user and g.user['id'] == user_id:
        flash('You cannot delete your own admin account.', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        delete_user_and_related(app.config['DATABASE'], user_id)
        flash('User deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete user: {str(e)}', 'error')
    return redirect(url_for('admin_dashboard'))

# Delete a single history item
@app.route('/remove_history/<int:analysis_id>', methods=['POST'])
def remove_history(analysis_id: int):
    if not g.user:
        return jsonify({'success': False, 'message': 'Please log in to continue.'}), 401
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cur = conn.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, g.user['id']))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return jsonify({'success': False, 'message': 'Analysis not found.'}), 404
        return jsonify({'success': True, 'message': 'History item removed.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error removing history: {str(e)}'}), 500

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
            # Normalize strange labels from LLM, e.g., typos or unknown names
            lang_norm = re.sub(r'[^a-z\+\#]', '', (lm_lang or '').lower())
            # Map common variants
            aliases = {
                'csharp': 'csharp', 'cs': 'csharp',
                'cplusplus': 'cpp', 'c\+\+': 'cpp', 'cpp': 'cpp', 'c': 'cpp',
                'js': 'javascript', 'node': 'javascript', 'javascript': 'javascript',
                'ts': 'typescript', 'typescript': 'typescript',
                'py': 'python', 'python': 'python',
            }
            lang_mapped = aliases.get(lang_norm, lang_norm)
            if lang_mapped in KNOWN_LANGUAGES:
                detected_language = lang_mapped
                detected_source = 'llm'
            else:
                # Treat as unknown if not in our vocabulary
                detected_language = 'unknown'
                detected_source = 'llm'
        else:
            check = check_code(code, 'auto')
            detected_language = check.get('language') or 'unknown'

        # Always use detected language
        language = detected_language

        # Heuristic quick signals for non-code / weak code format
        is_mostly_words = bool(re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}", code)) and not bool(re.search(r"\{|\}|;|=>|def\s|class\s|import\s|function\s|#|//|/\*", code))
        too_short_for_language = len(code.splitlines()) <= 2 and len(code) < 30

        # Force neutral outcome for non-programming-language inputs
        force_neutral = str(language or '').strip().lower() in (
            'unknown', 'none', 'text', 'plain text', 'not a programming language', 'not_a_language'
        ) or is_mostly_words or too_short_for_language

        heuristic = analyze_code(code, language)
        llm_result = classify_with_lmstudio(code, language) if not force_neutral else {
            'label': 'Uncertain (LLM)',
            'score': 50.0,
            'explanation': 'Language not identified or weak code structure; treating as not a programming language.',
        }
        
        # Deep Learning Analysis
        deep_learning_result = analyze_code_deep_learning(code, language) if not force_neutral else {
            'label': 'Uncertain',
            'score': 50.0,
            'confidence': 0.5,
            'explanation': 'Language not identified or weak code structure; neutral classification applied.'
        }

        # Build feedback with priority: Deep Learning > LLM > Heuristic
        feedback = None
        try:
            # If neutral is forced, short-circuit to Uncertain (50%)
            if force_neutral:
                score = 50.0
                feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain', 'source': 'Language detection' }
            # Try Deep Learning first (most accurate)
            elif deep_learning_result and deep_learning_result.get('score') is not None:
                score = deep_learning_result['score']
                if score > 75:
                    feedback = { 'title': f"AI-generated ({int(score)}%)", 'kind': 'ai', 'source': 'Deep Learning' }
                elif score < 25:
                    feedback = { 'title': f"Human-written ({int(score)}%)", 'kind': 'human', 'source': 'Deep Learning' }
                else:
                    feedback = { 'title': f"Uncertain ({int(score)}%)", 'kind': 'uncertain', 'source': 'Deep Learning' }
            
            # Fallback to LLM if Deep Learning fails
            elif llm_result and llm_result.get('label') and 'Unavailable' not in llm_result.get('label'):
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

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username:
            flash('Please enter your username.', 'error')
            return redirect(url_for('forgot_password'))
        
        # Check if user exists
        user = get_user_by_username(app.config['DATABASE'], username)
        if not user:
            flash('Username not found.', 'error')
            return redirect(url_for('forgot_password'))
        
        # Flag this user as requesting a reset
        try:
            conn = sqlite3.connect(app.config['DATABASE'])
            conn.execute("UPDATE users SET reset_requested = 1 WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()
        except Exception:
            pass
        
        # Redirect to admin dashboard for password reset
        flash(f'Password reset requested for user: {username}. An admin can now set a new password.', 'info')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('forgot_password.html')

@app.route('/admin/change_password/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_password(user_id: int):
    try:
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            flash('Please fill in all password fields.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Update password and clear reset flag
        conn = sqlite3.connect(app.config['DATABASE'])
        conn.execute(
            "UPDATE users SET password_hash = ?, reset_requested = 0 WHERE id = ?",
            (generate_password_hash(new_password), user_id)
        )
        conn.commit()
        conn.close()
        
        # Get username for flash message
        user = get_user_by_id(app.config['DATABASE'], user_id)
        username = user['username'] if user else 'Unknown'
        flash(f'Password changed successfully for user: {username}', 'success')
        
    except Exception as e:
        flash(f'Failed to change password: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
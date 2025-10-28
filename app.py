import os
import sqlite3
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from models import initialize_database, get_user_by_username, create_user, create_analysis, get_recent_analyses, create_uploaded_file, get_uploaded_files
from models import list_all_users, delete_user_and_related, get_user_count
from models import approve_user, get_user_by_id, update_user_role
from models import save_uploaded_file, get_uploaded_file, submit_activity
from models import create_group, get_teacher_groups, get_group_by_id, get_group_members
from models import join_group, approve_group_member, decline_group_member
from models import create_activity, get_group_activities, get_student_activities
from models import get_activity_submissions, get_student_submissions, grade_submission
from models import get_all_groups, get_available_groups_for_student, get_student_activity_participation
from models import get_student_submission_for_activity
from models import get_analysis_by_id
from detector import analyze_code
from code_check import check_code, validate_language_match
from deep_learning_detector import analyze_code_deep_learning
from enhanced_detector import analyze_code_with_enhanced_dataset

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['DATABASE'] = 'database.sqlite3'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions - only Java and Python
ALLOWED_EXTENSIONS = {
    'py': 'python',
    'java': 'java'
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

def teacher_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if g.user.get('role') not in ['teacher', 'admin']:
            flash('Teacher access required.', 'error')
            return redirect(url_for('dashboard'))
        return view_func(*args, **kwargs)
    return wrapped

def student_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        if g.user.get('role') not in ['student', 'teacher', 'admin']:
            flash('Student access required.', 'error')
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
    
    # Redirect based on user role
    user_role = g.user.get('role', 'student')
    
    if user_role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user_role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    else:  # student
        return redirect(url_for('student_dashboard'))

@app.route('/student_dashboard')
@student_required
def student_dashboard():
    # Get student's activities and submissions
    activities = get_student_activities(app.config['DATABASE'], g.user['id'])
    submissions = get_student_submissions(app.config['DATABASE'], g.user['id'])
    return render_template('student_dashboard.html', activities=activities, submissions=submissions)

@app.route('/teacher_dashboard')
@teacher_required
def teacher_dashboard():
    # Get teacher's groups and activities
    groups = get_teacher_groups(app.config['DATABASE'], g.user['id'])
    return render_template('teacher_dashboard.html', groups=groups)

@app.route('/browse_groups')
@student_required
def browse_groups():
    """Browse available groups to join - for students"""
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    # Get available groups for this student
    groups = get_available_groups_for_student(app.config['DATABASE'], g.user['id'])
    return render_template('browse_groups.html', groups=groups)

@app.route('/groups')
def groups():
    """Groups page - accessible by teachers and admins"""
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    user_role = g.user.get('role', 'student')
    is_admin = g.user.get('is_admin') or user_role == 'admin'
    is_teacher = user_role == 'teacher'
    
    if not (is_admin or is_teacher):
        flash('Access denied. Teacher or admin role required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get groups based on user role
    if is_admin:
        all_groups = get_all_groups(app.config['DATABASE'])
        return render_template('groups.html', groups=all_groups, user_role='admin')
    else:
        # Teacher sees their own groups
        groups = get_teacher_groups(app.config['DATABASE'], g.user['id'])
        return render_template('groups.html', groups=groups, user_role='teacher')

@app.route('/code_analysis')
def code_analysis():
    # Allow teachers and admins to access code analysis
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    user_role = g.user.get('role', 'student')
    if user_role not in ['teacher', 'admin'] and not g.user.get('is_admin'):
        flash('Access denied. Teacher or admin role required.', 'error')
        return redirect(url_for('dashboard'))
    history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
    uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
    return render_template('dashboard.html', history=history, uploaded_files=uploaded_files)

@app.route('/history/latest')
def history_latest():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    try:
        history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=1)
        latest = history[0] if history else None
        if not latest:
            flash('No analyses yet.', 'info')
            return redirect(url_for('dashboard'))
        # Render dashboard showing latest code in the code area
        uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
        return render_template(
            'dashboard.html',
            code_input=latest.get('code') or '',
            history=get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10),
            uploaded_files=uploaded_files,
            language=latest.get('language')
        )
    except Exception as e:
        app.logger.error(f"Failed to load latest analysis: {e}")
        flash('Failed to load latest analysis.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/history/<int:analysis_id>')
def history_view(analysis_id: int):
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    try:
        item = get_analysis_by_id(app.config['DATABASE'], g.user['id'], analysis_id)
        if not item:
            flash('Analysis not found.', 'error')
            return redirect(url_for('dashboard'))
        uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
        # Do NOT re-analyze; and do NOT show any analysis card
        code = item.get('code') or ''
        return render_template(
            'dashboard.html',
            code_input=code,
            history=get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10),
            uploaded_files=uploaded_files,
            language=item.get('language')
        )
    except Exception as e:
        app.logger.error(f"Failed to view analysis {analysis_id}: {e}")
        flash('Failed to open analysis.', 'error')
        return redirect(url_for('dashboard'))

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

# Text analysis endpoints removed

@app.route('/detect_enhanced', methods=['POST'])
def detect_enhanced():
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        code = request.form.get('code', '').strip()
        file_id = request.form.get('file_id')
        
        if not code:
            flash('Please paste some code.', 'error')
            return redirect(url_for('dashboard'))
        
        # Enhanced code analysis using comprehensive dataset
        enhanced_result = analyze_code_with_enhanced_dataset(code, 'auto')
        
        # Record analysis
        try:
            create_analysis(
                app.config['DATABASE'],
                g.user['id'],
                code,
                'auto',
                enhanced_result['final_prediction']['label'],
                enhanced_result['final_prediction']['score'],
                True,  # check_ok
                [],    # no errors
                int(file_id) if file_id else None,
                'code_enhanced'
            )
        except Exception as e:
            app.logger.warning(f"Failed to record enhanced analysis: {e}")
        
        history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
        uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
        
        return render_template(
            'dashboard.html',
            enhanced_result=enhanced_result,
            code_input=code,
            history=history,
            uploaded_files=uploaded_files,
            analysis_type='code_enhanced'
        )
                         
    except Exception as e:
        app.logger.error(f"Enhanced code analysis failed: {e}")
        flash('An error occurred during enhanced analysis. Please try again.', 'error')
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
        # Language detection removed - using heuristic detection only
        lm_lang = None
        if False:  # Disabled LLM language detection
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
        llm_result = {
            'label': 'Uncertain (LLM)',
            'score': 50.0,
            'explanation': 'LLM analysis disabled - using enhanced analysis only.',
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
                content_type='code'
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

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id: int):
    try:
        new_role = request.form.get('new_role', '').strip()
        
        if new_role not in ['student', 'teacher', 'admin']:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Prevent self-demotion from admin
        if g.user and g.user['id'] == user_id and new_role != 'admin':
            flash('You cannot change your own admin role.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        update_user_role(app.config['DATABASE'], user_id, new_role)
        
        # Get username for flash message
        user = get_user_by_id(app.config['DATABASE'], user_id)
        username = user['username'] if user else 'Unknown'
        flash(f'Role changed successfully for user: {username} (now {new_role})', 'success')
        
    except Exception as e:
        flash(f'Failed to change role: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_group', methods=['GET', 'POST'])
@admin_required
def admin_create_group():
    """Admin can create groups and assign them to teachers"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        teacher_id = request.form.get('teacher_id', '').strip()
        
        if not name:
            flash('Group name is required.', 'error')
            return redirect(url_for('admin_create_group'))
        
        if not teacher_id:
            flash('Teacher must be selected.', 'error')
            return redirect(url_for('admin_create_group'))
        
        try:
            group_id = create_group(app.config['DATABASE'], name, description, int(teacher_id))
            flash(f'Group "{name}" created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Failed to create group: {str(e)}', 'error')
    
    # Get all teachers for the dropdown
    users = list_all_users(app.config['DATABASE'])
    teachers = [u for u in users if u.get('role') == 'teacher' and u.get('is_approved')]
    
    return render_template('admin_create_group.html', teachers=teachers)

# Group Management Routes
@app.route('/teacher/create_group', methods=['GET', 'POST'])
@teacher_required
def create_group_route():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Group name is required.', 'error')
            return redirect(url_for('create_group_route'))
        
        try:
            group_id = create_group(app.config['DATABASE'], name, description, g.user['id'])
            flash(f'Group "{name}" created successfully!', 'success')
            return redirect(url_for('view_group', group_id=group_id))
        except Exception as e:
            flash(f'Failed to create group: {str(e)}', 'error')
    
    return render_template('create_group.html')

@app.route('/teacher/group/<int:group_id>')
def view_group(group_id):
    # Check if user is logged in
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    # Allow teachers, admins, and the group's teacher to view
    group = get_group_by_id(app.config['DATABASE'], group_id)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('dashboard'))
    
    # Check permissions
    user_role = g.user.get('role', 'student')
    is_admin = g.user.get('is_admin') or user_role == 'admin'
    is_teacher = user_role == 'teacher'
    is_group_teacher = group['teacher_id'] == g.user['id']
    
    if not (is_admin or (is_teacher and is_group_teacher)):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    members = get_group_members(app.config['DATABASE'], group_id)
    activities = get_group_activities(app.config['DATABASE'], group_id)
    
    # Get activity participation for each member
    member_participation = {}
    for member in members:
        if member['status'] == 'approved':
            member_participation[member['user_id']] = get_student_activity_participation(
                app.config['DATABASE'], group_id, member['user_id']
            )
    
    return render_template('view_group.html', group=group, members=members, activities=activities, member_participation=member_participation)

@app.route('/teacher/group/<int:group_id>/approve/<int:user_id>', methods=['POST'])
@teacher_required
def approve_group_member_route(group_id, user_id):
    try:
        approve_group_member(app.config['DATABASE'], group_id, user_id)
        flash('Member approved successfully.', 'success')
    except Exception as e:
        flash(f'Failed to approve member: {str(e)}', 'error')
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/teacher/group/<int:group_id>/decline/<int:user_id>', methods=['POST'])
@teacher_required
def decline_group_member_route(group_id, user_id):
    try:
        decline_group_member(app.config['DATABASE'], group_id, user_id)
        flash('Member declined successfully.', 'success')
    except Exception as e:
        flash(f'Failed to decline member: {str(e)}', 'error')
    return redirect(url_for('view_group', group_id=group_id))

# Student Group Routes
@app.route('/student/join_group/<int:group_id>', methods=['POST'])
@student_required
def join_group_route(group_id):
    try:
        success = join_group(app.config['DATABASE'], group_id, g.user['id'])
        if success:
            flash('Request to join group sent successfully!', 'success')
        else:
            flash('You are already a member of this group.', 'info')
    except Exception as e:
        flash(f'Failed to join group: {str(e)}', 'error')
    return redirect(url_for('student_dashboard'))

# Activity Management Routes
@app.route('/teacher/group/<int:group_id>/create_activity', methods=['GET', 'POST'])
@teacher_required
def create_activity_route(group_id):
    group = get_group_by_id(app.config['DATABASE'], group_id)
    if not group or group['teacher_id'] != g.user['id']:
        flash('Group not found.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        content = request.form.get('content', '').strip()
        activity_type = request.form.get('activity_type', 'text')
        due_date = request.form.get('due_date', '').strip() or None
        
        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('create_activity_route', group_id=group_id))
        
        try:
            activity_id = create_activity(
                app.config['DATABASE'], group_id, g.user['id'], 
                title, description, content, activity_type, due_date
            )
            flash('Activity created successfully!', 'success')
            return redirect(url_for('view_group', group_id=group_id))
        except Exception as e:
            flash(f'Failed to create activity: {str(e)}', 'error')
    
    return render_template('create_activity.html', group=group)

@app.route('/student/activity/<int:activity_id>')
@student_required
def view_activity(activity_id):
    # Get activity details and check if student has access
    activities = get_student_activities(app.config['DATABASE'], g.user['id'])
    activity = next((a for a in activities if a['id'] == activity_id), None)
    
    if not activity:
        flash('Activity not found or access denied.', 'error')
        return redirect(url_for('student_dashboard'))
    
    # Fetch current student's submission, if any
    submission = get_student_submission_for_activity(app.config['DATABASE'], g.user['id'], activity_id)
    return render_template('view_activity.html', activity=activity, submission=submission)

@app.route('/student/activity/<int:activity_id>/submit', methods=['POST'])
@student_required
def submit_activity_route(activity_id):
    content = request.form.get('content', '').strip()
    uploaded_file = request.files.get('file')
    
    # Validate that either content or file is provided
    if not content and not uploaded_file:
        flash('Either text content or a file upload is required.', 'error')
        return redirect(url_for('view_activity', activity_id=activity_id))
    
    file_id = None
    
    # Handle file upload
    if uploaded_file and uploaded_file.filename:
        if not allowed_file(uploaded_file.filename):
            flash('Only Java (.java) and Python (.py) files are allowed.', 'error')
            return redirect(url_for('view_activity', activity_id=activity_id))
        
        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Generate secure filename
        filename = secure_filename(uploaded_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            uploaded_file.save(file_path)
            file_size = os.path.getsize(file_path)
            content_type = uploaded_file.content_type or 'application/octet-stream'
            
            # Save file info to database
            file_id = save_uploaded_file(
                app.config['DATABASE'],
                unique_filename,
                uploaded_file.filename,
                file_path,
                file_size,
                content_type,
                g.user['id']
            )
        except Exception as e:
            flash(f'Error uploading file: {str(e)}', 'error')
            return redirect(url_for('view_activity', activity_id=activity_id))
    
    try:
        submit_activity(app.config['DATABASE'], activity_id, g.user['id'], content, file_id)
        flash('Activity submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    except ValueError as e:
        # Already submitted
        flash(str(e), 'info')
        return redirect(url_for('view_activity', activity_id=activity_id))
    except Exception as e:
        flash(f'Failed to submit activity: {str(e)}', 'error')
        return redirect(url_for('view_activity', activity_id=activity_id))

@app.route('/teacher/activity/<int:activity_id>/submissions')
@teacher_required
def view_activity_submissions(activity_id):
    submissions = get_activity_submissions(app.config['DATABASE'], activity_id)
    return render_template('activity_submissions.html', submissions=submissions)

@app.route('/teacher/submission/<int:submission_id>/grade', methods=['POST'])
@teacher_required
def grade_submission_route(submission_id):
    grade = request.form.get('grade', '').strip()
    feedback = request.form.get('feedback', '').strip()
    
    try:
        grade_float = float(grade) if grade else None
        grade_submission(app.config['DATABASE'], submission_id, grade_float, feedback)
        flash('Submission graded successfully!', 'success')
    except ValueError:
        flash('Invalid grade format.', 'error')
    except Exception as e:
        flash(f'Failed to grade submission: {str(e)}', 'error')
    
    return redirect(url_for('view_activity_submissions', activity_id=request.form.get('activity_id')))

@app.route('/teacher/submission/<int:student_id>/<int:activity_id>')
def view_student_submission(student_id, activity_id):
    """View a specific student's answer to a specific activity"""
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    # Check if user has permission (teacher or admin)
    user_role = g.user.get('role', 'student')
    if user_role not in ['teacher', 'admin'] and not g.user.get('is_admin'):
        flash('Access denied. Teacher or admin role required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the submission
    submission = get_student_submission_for_activity(app.config['DATABASE'], student_id, activity_id)
    
    if not submission:
        flash('Submission not found.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get activity details
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
    activity = cur.fetchone()
    conn.close()
    
    if not activity:
        flash('Activity not found.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('view_student_submission.html', 
                          submission=submission, 
                          activity=dict(activity))
if __name__ == '__main__':
    app.run(debug=True)
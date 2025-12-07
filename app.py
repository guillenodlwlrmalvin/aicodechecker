import os
import sqlite3
import re
import uuid
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit, disconnect

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, continue without it
    pass
from models import initialize_database, get_user_by_username, create_user, create_analysis, get_recent_analyses, create_uploaded_file, get_uploaded_files
from models import list_all_users, delete_user_and_related, get_user_count
from models import approve_user, get_user_by_id, update_user_role
from models import set_user_verification_token, get_user_by_verification_token, get_user_by_verification_code, mark_user_verified, update_user_password
from models import save_uploaded_file, get_uploaded_file, submit_activity, update_submission_analysis
from models import create_group, get_teacher_groups, get_group_by_id, get_group_members, delete_group
from models import join_group, approve_group_member, decline_group_member
from models import create_activity, get_group_activities, get_student_activities, get_activity_by_id
from models import get_activity_submissions, get_student_submissions, grade_submission
from models import create_notification, get_user_notifications, get_unread_notification_count, mark_notification_as_read, mark_all_notifications_as_read, get_all_admin_users
from models import get_all_groups, get_available_groups_for_student, get_student_activity_participation
from models import get_student_submission_for_activity
from models import get_analysis_by_id
from detector import analyze_code
from code_check import check_code, validate_language_match
from deep_learning_detector import analyze_code_deep_learning
from enhanced_detector import analyze_code_with_enhanced_dataset
from code_executor import CodeExecutor
from interactive_executor import InteractiveExecutor
from google_auth import google_auth_bp


# Flask application & configuration
app = Flask(__name__)
# Use the standard Flask secret_key attribute
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')
# Configure session cookies to persist across redirects (needed for OAuth)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cross-site redirects for OAuth
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['DATABASE'] = 'database.sqlite3'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
# Gmail SMTP credentials – must be provided via environment variables:
#   GMAIL_USER = your Gmail address (e.g. myapp@gmail.com)
#   GMAIL_PASS = Gmail App Password (16‑character value from Google)
# No hardcoded fallbacks - require environment variables
gmail_user = os.environ.get('GMAIL_USER')
gmail_pass = os.environ.get('GMAIL_PASS')

app.config['MAIL_GMAIL_USER'] = gmail_user
app.config['MAIL_GMAIL_PASS'] = gmail_pass

# Log email configuration status (without exposing password)
if gmail_user and gmail_pass:
    app.logger.info(f"Gmail SMTP configured for: {gmail_user}")
else:
    app.logger.warning("Gmail SMTP credentials not configured - email sending will be disabled")

# Register blueprints (Google OAuth)
app.register_blueprint(google_auth_bp)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Store active execution sessions
active_sessions = {}

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
    """Check if file is allowed - only Python and Java files are allowed for upload"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    # Only allow Python and Java files
    return ext in ['py', 'java']


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


# Import email utilities
from email_utils import send_verification_email as _send_verification_email, send_welcome_email as _send_welcome_email


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    import random
    return str(random.randint(100000, 999999))


def send_verification_email(recipient_email: str, code: str) -> None:
    """Send a Gmail-based verification email with 6-digit code if SMTP is configured.
    This is for EMAIL/PASSWORD registration - user must verify before login.
    """
    # Call the utility function
    _send_verification_email(recipient_email, code, app)
    
    # If SMTP not configured, show fallback in UI
    if not app.config.get('MAIL_GMAIL_USER') or not app.config.get('MAIL_GMAIL_PASS'):
        try:
            flash('Email sending is not configured. Your verification code is:', 'warning')
            flash(code, 'info')
        except RuntimeError:
            # flash may fail if called outside a request context; ignore
            pass


def send_welcome_email(recipient_email: str, name: str) -> None:
    """Send a welcome/confirmation email to Google SSO users.
    This is for GOOGLE SSO registration - user is already verified by Google.
    """
    _send_welcome_email(recipient_email, name, app)

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
        username = request.form['username'].strip()
        password = request.form['password']
        confirm = request.form.get('confirm', '')
        
        if not username or not password or not confirm:
            flash('Please fill in all fields.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif '@' not in username or not username.lower().endswith('@gmail.com'):
            flash('Please register with a valid Gmail address (example@gmail.com).', 'error')
        else:
            try:
                # If user already exists, handle gracefully instead of raising a DB error
                existing = get_user_by_username(app.config['DATABASE'], username)
                if existing:
                    if existing.get('is_approved'):
                        flash('This email is already registered. Please log in or use password reset.', 'warning')
                        return redirect(url_for('login'))
                    # User exists but not verified – resend verification code
                    from datetime import datetime, timedelta
                    code = generate_verification_code()
                    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
                    set_user_verification_token(app.config['DATABASE'], existing['id'], code, expires_at)
                    send_verification_email(username, code)
                    flash('This email is already registered but not verified. A new verification code has been sent to your email.', 'info')
                    return redirect(url_for('verify_code'))

                # First user becomes admin automatically and approved
                is_first_user = get_user_count(app.config['DATABASE']) == 0
                user_id = create_user(
                    app.config['DATABASE'],
                    username,
                    generate_password_hash(password),
                    is_admin=is_first_user,
                    is_approved=is_first_user,
                )
                
                if is_first_user:
                    flash('Registration successful! Your account has admin privileges and is approved.', 'success')
                else:
                    # Generate 6-digit verification code and send Gmail confirmation
                    from datetime import datetime, timedelta
                    code = generate_verification_code()
                    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
                    set_user_verification_token(app.config['DATABASE'], user_id, code, expires_at)
                    send_verification_email(username, code)
                    if app.config.get('MAIL_GMAIL_USER') and app.config.get('MAIL_GMAIL_PASS'):
                        flash('Registration successful! Please check your Gmail inbox for the 6-digit verification code.', 'info')
                    else:
                        flash('Registration successful! Enter the verification code shown above to activate your account.', 'info')
                return redirect(url_for('verify_code'))
            except sqlite3.IntegrityError as e:
                # Fallback friendly message for any unique-constraint or integrity errors
                app.logger.error(f"Registration integrity error: {e}")
                flash('This email is already registered. Please log in or use password reset.', 'error')
            except Exception as e:
                app.logger.error(f"Registration failed: {e}")
                flash('Registration failed due to an unexpected error. Please try again later.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_username(app.config['DATABASE'], username)
        
        if not user:
            flash('Invalid username or password.', 'error')
        else:
            # Check if user has a password set
            password_hash = user.get('password_hash', '').strip() if user.get('password_hash') else ''
            
            app.logger.debug(f"Login attempt for user: {username}, has_password: {bool(password_hash)}, has_google_id: {bool(user.get('google_id'))}")
            
            # If user has google_id but no password, suggest Google login
            if user.get('google_id') and not password_hash:
                flash('This account was created with Google. Please use "Sign in with Google" instead.', 'warning')
            # If user has no password at all
            elif not password_hash:
                flash('Invalid username or password.', 'error')
            # Check password
            else:
                password_valid = check_password_hash(password_hash, password)
                app.logger.debug(f"Password check result: {password_valid}")
                if not password_valid:
                    flash('Invalid username or password.', 'error')
                else:
                    # Valid password check passed
                    if not user.get('is_approved'):
                        flash('Your email is not verified yet. Please check your inbox for the verification link.', 'warning')
                        return redirect(url_for('login'))
                    session['user_id'] = username
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/verify', methods=['GET', 'POST'])
def verify_code():
    """Verification page where users enter their 6-digit code."""
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if not code or len(code) != 6 or not code.isdigit():
            flash('Please enter a valid 6-digit code.', 'error')
            return render_template('verify_code.html')
        
        user = get_user_by_verification_code(app.config['DATABASE'], code)
        if not user:
            flash('Invalid or expired verification code. Please check your email and try again.', 'error')
            return render_template('verify_code.html')
        
        try:
            mark_user_verified(app.config['DATABASE'], user['id'])
            # Store user email in session for password creation
            session['pending_password_user'] = user['username']
            session['pending_password_user_id'] = user['id']
            # Check if user already has a password (email/password registration) or needs to create one (Google OAuth)
            if not user.get('password_hash') or user.get('password_hash').strip() == '':
                flash('Email verified successfully! Please create a password for your account.', 'success')
                return redirect(url_for('create_password'))
            else:
                flash('Email verified successfully! You can now log in.', 'success')
                session.pop('pending_password_user', None)
                session.pop('pending_password_user_id', None)
                return redirect(url_for('login'))
        except Exception as e:
            app.logger.error(f"Failed to verify code for user {user['id']}: {e}")
            flash('Failed to verify code. Please try again later.', 'error')
    
    return render_template('verify_code.html')


@app.route('/create-password', methods=['GET', 'POST'])
def create_password():
    """Password creation page after email verification."""
    # Check if user is in the password creation flow
    pending_user = session.get('pending_password_user')
    pending_user_id = session.get('pending_password_user_id')
    
    if not pending_user or not pending_user_id:
        flash('Please verify your email first.', 'warning')
        return redirect(url_for('verify_code'))
    
    # Get user to check if they already have a password
    user = get_user_by_username(app.config['DATABASE'], pending_user)
    if not user:
        flash('User not found.', 'error')
        session.pop('pending_password_user', None)
        session.pop('pending_password_user_id', None)
        return redirect(url_for('login'))
    
    # If user already has a password, redirect to login
    if user.get('password_hash') and user.get('password_hash').strip() != '':
        flash('You already have a password. Please log in.', 'info')
        session.pop('pending_password_user', None)
        session.pop('pending_password_user_id', None)
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('create_password.html', email=pending_user)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('create_password.html', email=pending_user)
        
        try:
            # Update user password
            password_hash = generate_password_hash(password)
            app.logger.info(f"Creating password for user {pending_user_id} (email: {pending_user})")
            update_user_password(app.config['DATABASE'], pending_user_id, password_hash)
            
            # Verify password was saved correctly
            updated_user = get_user_by_username(app.config['DATABASE'], pending_user)
            if updated_user and updated_user.get('password_hash'):
                app.logger.info(f"Password successfully saved for user {pending_user_id}")
                # Test password verification
                if check_password_hash(updated_user['password_hash'], password):
                    app.logger.info(f"Password verification test passed for user {pending_user_id}")
                else:
                    app.logger.error(f"Password verification test FAILED for user {pending_user_id}")
            else:
                app.logger.error(f"Password was not saved correctly for user {pending_user_id}")
            
            # Clear pending session
            session.pop('pending_password_user', None)
            session.pop('pending_password_user_id', None)
            
            flash('Password created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            app.logger.error(f"Failed to create password for user {pending_user_id}: {e}", exc_info=True)
            flash('Failed to create password. Please try again.', 'error')
    
    return render_template('create_password.html', email=pending_user)


@app.route('/verify/<token>')
def verify_email(token):
    """Legacy verification endpoint for backward compatibility (redirects to code verification)."""
    flash('Please use the verification code sent to your email instead.', 'info')
    return redirect(url_for('verify_code'))

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
    # Allow any authenticated user to access code analysis
    if not g.user:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))
    
    # Get code from query parameter if provided
    code_input = request.args.get('code', '')
    
    history = get_recent_analyses(app.config['DATABASE'], g.user['id'], limit=10)
    uploaded_files = get_uploaded_files(app.config['DATABASE'], g.user['id'], limit=20)
    return render_template('dashboard.html', history=history, uploaded_files=uploaded_files, code_input=code_input)

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
    
    # Only allow Python and Java files
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
        flash('Only Python (.py) and Java (.java) files are allowed.', 'error')
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
        
        # Enforce 1,000-line limit by rejecting submissions that reach/exceed the cap
        lines = code.split('\n')
        if len(lines) >= 1000:
            flash('Line limit reached (1,000). Please trim your code before analyzing.', 'error')
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


@app.route('/run_code', methods=['POST'])
def run_code():
    """Execute code and return results"""
    if not g.user:
        return jsonify({'success': False, 'error': 'Please log in to continue.'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request. No data provided.'}), 400
            
        code = data.get('code', '').strip()
        language = data.get('language', 'auto').strip().lower()
        input_data = data.get('input', '').strip()  # Get input data if provided
        
        if not code:
            return jsonify({'success': False, 'error': 'Please provide code to execute.'}), 400
        
        # Auto-detect language if needed
        if language == 'auto' or not language:
            # Try to detect from code - check Java first (more distinctive patterns)
            code_lower = code.lower()
            
            # Java indicators (check first)
            java_indicators = [
                'public class',
                'public static void main',
                'import java.',
                'system.out.println',
                'scanner',
                'private ',
                'protected ',
                'extends ',
                'implements '
            ]
            
            # Python indicators
            python_indicators = [
                'def ',
                'if __name__',
                'print(',
                'import '  # Generic import (but Java has 'import java.')
            ]
            
            has_java = any(indicator in code_lower for indicator in java_indicators)
            has_python = any(indicator in code_lower for indicator in python_indicators)
            
            # Prioritize Java if both are present (Java patterns are more specific)
            if has_java:
                language = 'java'
            elif has_python:
                language = 'python'
            else:
                return jsonify({
                    'success': False, 
                    'error': 'Could not auto-detect language. Please specify Python or Java.'
                }), 400
        
        # Log the execution attempt for debugging
        app.logger.info(f"Executing {language} code (length: {len(code)} chars)")
        
        # Execute the code with optional input
        result = CodeExecutor.execute_code(code, language, input_data=input_data if input_data else None)
        
        # Log the result for debugging
        app.logger.info(f"Execution result: success={result.get('success')}, return_code={result.get('return_code')}")
        if not result.get('success'):
            app.logger.warning(f"Execution error: {result.get('error', 'Unknown error')}")
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(f"Code execution failed: {e}\n{error_trace}")
        return jsonify({
            'success': False,
            'error': f'An error occurred during code execution: {str(e)}\n\nTraceback:\n{error_trace}',
            'output': '',
            'execution_time': 0
        }), 500


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
        
        # Notify all admins about password reset request
        admins = get_all_admin_users(app.config['DATABASE'])
        for admin in admins:
            create_notification(
                app.config['DATABASE'],
                admin['id'],
                'password_reset',
                'Password Reset Requested',
                f"User '{username}' has requested a password reset. Please change their password in the admin dashboard.",
                user['id'],
                'user'
            )
        
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
            
            # Get teacher info for notification
            teacher = get_user_by_id(app.config['DATABASE'], int(teacher_id))
            teacher_name = teacher['username'] if teacher else 'Unknown'
            
            # Notify all admins about new group creation (except the one creating if they're admin)
            admins = get_all_admin_users(app.config['DATABASE'])
            for admin in admins:
                # Skip notification if admin is creating the group themselves
                if admin['id'] != g.user['id']:
                    create_notification(
                        app.config['DATABASE'],
                        admin['id'],
                        'new_group',
                        'New Group Created',
                        f"Group '{name}' has been created by admin for teacher '{teacher_name}'",
                        group_id,
                        'group'
                    )
            
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
            
            # Notify all admins about new group creation
            admins = get_all_admin_users(app.config['DATABASE'])
            for admin in admins:
                create_notification(
                    app.config['DATABASE'],
                    admin['id'],
                    'new_group',
                    'New Group Created',
                    f"Teacher '{g.user['username']}' has created a new group: '{name}'",
                    group_id,
                    'group'
                )
            
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

@app.route('/teacher/group/<int:group_id>/delete', methods=['POST'])
@teacher_required
def delete_group_route(group_id):
    """Teacher can delete their own groups"""
    group = get_group_by_id(app.config['DATABASE'], group_id)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    # Check if the current user is the teacher who created this group
    if group['teacher_id'] != g.user['id']:
        flash('You can only delete groups you created.', 'error')
        return redirect(url_for('view_group', group_id=group_id))
    
    try:
        group_name = group['name']
        delete_group(app.config['DATABASE'], group_id)
        flash(f'Group "{group_name}" deleted successfully.', 'success')
        return redirect(url_for('teacher_dashboard'))
    except Exception as e:
        flash(f'Failed to delete group: {str(e)}', 'error')
        return redirect(url_for('view_group', group_id=group_id))

@app.route('/admin/group/<int:group_id>/delete', methods=['POST'])
@admin_required
def admin_delete_group_route(group_id):
    """Admin can delete any group"""
    group = get_group_by_id(app.config['DATABASE'], group_id)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        group_name = group['name']
        delete_group(app.config['DATABASE'], group_id)
        flash(f'Group "{group_name}" deleted successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Failed to delete group: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

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
            
            # Notify all approved students in the group about the new activity
            members = get_group_members(app.config['DATABASE'], group_id)
            for member in members:
                if member['status'] == 'approved' and member['role'] == 'student':
                    due_date_msg = f" Due date: {due_date}" if due_date else ""
                    create_notification(
                        app.config['DATABASE'],
                        member['user_id'],
                        'new_activity',
                        'New Activity: ' + title,
                        f"A new activity '{title}' has been added to your group.{due_date_msg}",
                        activity_id,
                        'activity'
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
        # Save submission record
        submission_id = submit_activity(app.config['DATABASE'], activity_id, g.user['id'], content, file_id)
        
        # Build code text for AI/human analysis
        code_text = content or ''
        if not code_text and file_id:
            # Load code from uploaded file on disk
            uploaded_info = get_uploaded_file(app.config['DATABASE'], file_id)
            if uploaded_info:
                file_path = uploaded_info.get('file_path')
                if file_path and os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            code_text = f.read()
                    except Exception:
                        code_text = ''
        
        # Run enhanced AI/human analysis if we have code
        if code_text:
            try:
                analysis_result = analyze_code_with_enhanced_dataset(code_text, 'auto')
                final_pred = analysis_result.get('final_prediction', {})
                ai_label = final_pred.get('label')
                ai_score = final_pred.get('score')
                explanation = json.dumps(analysis_result)
                if ai_label is not None and ai_score is not None:
                    update_submission_analysis(
                        app.config['DATABASE'],
                        submission_id,
                        ai_label,
                        float(ai_score),
                        explanation,
                    )
            except Exception as e:
                app.logger.error(f"Failed to auto-analyze submission {submission_id}: {e}")
        
        # Get activity details to notify teacher
        activity = get_activity_by_id(app.config['DATABASE'], activity_id)
        
        if activity:
            # Notify the teacher about the submission
            create_notification(
                app.config['DATABASE'],
                activity['teacher_id'],
                'submission',
                'New Submission',
                f"Student {g.user['username']} submitted the activity '{activity['title']}'",
                activity_id,
                'activity'
            )
        
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
    # Check for plagiarism if requested
    check_plagiarism = request.args.get('check_plagiarism', 'false').lower() == 'true'
    plagiarism_results = None
    if check_plagiarism:
        from plagiarism_detector import detect_plagiarism
        plagiarism_results = detect_plagiarism(submissions)
    return render_template('activity_submissions.html', submissions=submissions, 
                         plagiarism_results=plagiarism_results, activity_id=activity_id)

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

@app.route('/api/notifications')
def get_notifications():
    """Get notifications for the current user"""
    if not g.user:
        return jsonify({'notifications': [], 'unread_count': 0})
    
    notifications = get_user_notifications(app.config['DATABASE'], g.user['id'], limit=20)
    unread_count = get_unread_notification_count(app.config['DATABASE'], g.user['id'])
    
    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count
    })


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    if not g.user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    mark_notification_as_read(app.config['DATABASE'], notification_id, g.user['id'])
    return jsonify({'success': True})


@app.route('/api/notifications/read-all', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read"""
    if not g.user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    mark_all_notifications_as_read(app.config['DATABASE'], g.user['id'])
    return jsonify({'success': True})


@app.route('/api/notifications/check-deadlines')
def check_deadlines():
    """Check for upcoming deadlines and create notifications"""
    if not g.user or g.user.get('role') != 'student':
        return jsonify({'success': False})
    
    from datetime import datetime, timedelta
    
    # Get all activities for the student
    activities = get_student_activities(app.config['DATABASE'], g.user['id'])
    now = datetime.utcnow()
    
    for activity in activities:
        if activity.get('due_date') and not activity.get('has_submitted'):
            try:
                # Parse due_date (could be in various formats)
                due_date_str = activity['due_date']
                # Handle ISO format with or without timezone
                if 'T' in due_date_str:
                    if due_date_str.endswith('Z'):
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    else:
                        due_date = datetime.fromisoformat(due_date_str)
                else:
                    # If no time, assume end of day
                    due_date = datetime.fromisoformat(due_date_str + 'T23:59:59')
                
                # Make due_date timezone-aware if now is naive
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=None)
                if now.tzinfo is not None:
                    now = now.replace(tzinfo=None)
                
                # Check if deadline is within 24 hours
                time_until_deadline = due_date - now
                
                if timedelta(hours=0) < time_until_deadline <= timedelta(hours=24):
                    # Check if we already notified about this deadline
                    existing_notifications = get_user_notifications(
                        app.config['DATABASE'], 
                        g.user['id'], 
                        limit=50
                    )
                    
                    # Check if notification already exists for this deadline
                    already_notified = any(
                        n['related_id'] == activity['id'] and 
                        n['type'] == 'deadline' and
                        n['is_read'] == 0
                        for n in existing_notifications
                    )
                    
                    if not already_notified:
                        create_notification(
                            app.config['DATABASE'],
                            g.user['id'],
                            'deadline',
                            'Deadline Approaching',
                            f"Activity '{activity['title']}' is due in less than 24 hours!",
                            activity['id'],
                            'activity'
                        )
            except Exception:
                pass  # Skip invalid dates
    
    return jsonify({'success': True})


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
    
    # Decode AI analysis if available
    detailed_analysis = None
    if submission.get('ai_explanation'):
        try:
            detailed_analysis = json.loads(submission['ai_explanation'])
        except Exception:
            detailed_analysis = None
    
    # Get activity details
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
    activity = cur.fetchone()
    conn.close()
    
    if not activity:
        flash('Activity not found.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template(
        'view_student_submission.html',
        submission=submission,
        activity=dict(activity),
        detailed_analysis=detailed_analysis,
    )

# WebSocket events for interactive code execution
@socketio.on('start_interactive_execution')
def handle_start_execution(data):
    """Start an interactive code execution session"""
    from flask import request as flask_request
    # Get user from session
    user_id = flask_request.sid
    # We'll need to get user info differently - check session
    if 'user_id' not in session:
        emit('execution_error', {'error': 'Not authenticated'})
        return
    
    user = get_user_by_username(app.config['DATABASE'], session['user_id'])
    if not user:
        emit('execution_error', {'error': 'User not found'})
        return
    
    try:
        code = data.get('code', '').strip()
        language = data.get('language', 'auto').strip().lower()
        
        if not code:
            emit('execution_error', {'error': 'No code provided'})
            return
        
        # Auto-detect language if needed
        if language == 'auto' or not language:
            # Try to detect from code - check Java first (more distinctive patterns)
            code_lower = code.lower()
            
            # Java indicators (check first)
            java_indicators = [
                'public class',
                'public static void main',
                'import java.',
                'system.out.println',
                'scanner',
                'private ',
                'protected ',
                'extends ',
                'implements '
            ]
            
            # Python indicators
            python_indicators = [
                'def ',
                'if __name__',
                'print(',
                'import '  # Generic import (but Java has 'import java.')
            ]
            
            has_java = any(indicator in code_lower for indicator in java_indicators)
            has_python = any(indicator in code_lower for indicator in python_indicators)
            
            # Prioritize Java if both are present (Java patterns are more specific)
            if has_java:
                language = 'java'
            elif has_python:
                language = 'python'
            else:
                emit('execution_error', {'error': 'Could not auto-detect language'})
                return
        
        # Create session ID
        session_id = str(uuid.uuid4())
        
        # Create interactive executor
        executor = InteractiveExecutor(code, language, session_id)
        result = executor.start()
        
        if result.get('success'):
            # Store session
            active_sessions[session_id] = {
                'executor': executor,
                'user_id': user['id'],
                'language': language,
                'socket_id': flask_request.sid
            }
            emit('execution_started', {'session_id': session_id})
            
            # Start output polling
            socketio.start_background_task(poll_output, session_id, flask_request.sid)
        else:
            emit('execution_error', {'error': result.get('error', 'Failed to start execution')})
            
    except Exception as e:
        app.logger.error(f"Error starting interactive execution: {e}")
        emit('execution_error', {'error': f'Error: {str(e)}'})


@socketio.on('send_input')
def handle_send_input(data):
    """Send input to a running execution"""
    from flask import request as flask_request
    if 'user_id' not in session:
        emit('execution_error', {'error': 'Not authenticated'})
        return
    
    try:
        session_id = data.get('session_id')
        input_data = data.get('input', '')
        
        if not session_id or session_id not in active_sessions:
            emit('execution_error', {'error': 'Invalid session ID'})
            return
        
        session_data = active_sessions[session_id]
        
        # Verify user owns this session
        user = get_user_by_username(app.config['DATABASE'], session['user_id'])
        if not user or session_data['user_id'] != user['id']:
            emit('execution_error', {'error': 'Unauthorized'})
            return
        
        executor = session_data['executor']
        result = executor.send_input(input_data)
        
        if not result.get('success'):
            emit('execution_error', {'error': result.get('error')})
            
    except Exception as e:
        app.logger.error(f"Error sending input: {e}")
        emit('execution_error', {'error': f'Error: {str(e)}'})


@socketio.on('stop_execution')
def handle_stop_execution(data):
    """Stop a running execution"""
    from flask import request as flask_request
    if 'user_id' not in session:
        emit('execution_error', {'error': 'Not authenticated'})
        return
    
    try:
        session_id = data.get('session_id')
        
        if session_id and session_id in active_sessions:
            session_data = active_sessions[session_id]
            
            # Verify user owns this session
            user = get_user_by_username(app.config['DATABASE'], session['user_id'])
            if user and session_data['user_id'] == user['id']:
                executor = session_data['executor']
                executor.stop()
                del active_sessions[session_id]
                emit('execution_stopped', {'session_id': session_id})
        else:
            emit('execution_error', {'error': 'Invalid session ID'})
            
    except Exception as e:
        app.logger.error(f"Error stopping execution: {e}")
        emit('execution_error', {'error': f'Error: {str(e)}'})


@socketio.on('disconnect')
def handle_disconnect():
    """Clean up sessions when user disconnects"""
    # Clean up all sessions for this user
    if 'user_id' in session:
        user = get_user_by_username(app.config['DATABASE'], session['user_id'])
        if user:
            sessions_to_remove = [
                sid for sid, data in active_sessions.items()
                if data['user_id'] == user['id']
            ]
            for sid in sessions_to_remove:
                try:
                    active_sessions[sid]['executor'].stop()
                    del active_sessions[sid]
                except Exception:
                    pass


def poll_output(session_id, socket_id):
    """Background task to poll for output and emit to client"""
    while session_id in active_sessions:
        try:
            session_data = active_sessions[session_id]
            executor = session_data['executor']
            
            output_data = executor.get_output()
            
            if output_data.get('output'):
                socketio.emit('execution_output', {
                    'session_id': session_id,
                    'output': output_data['output']
                }, room=socket_id)
            
            if output_data.get('error'):
                socketio.emit('execution_error_output', {
                    'session_id': session_id,
                    'error': output_data['error']
                }, room=socket_id)
            
            if output_data.get('done'):
                socketio.emit('execution_finished', {
                    'session_id': session_id,
                    'return_code': output_data.get('return_code')
                }, room=socket_id)
                
                # Clean up
                if session_id in active_sessions:
                    del active_sessions[session_id]
                break
            
            socketio.sleep(0.1)  # Poll every 100ms
            
        except Exception as e:
            app.logger.error(f"Error polling output for session {session_id}: {e}")
            break


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
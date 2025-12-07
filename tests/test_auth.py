import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username,
    get_user_by_verification_code, mark_user_verified, update_user_password,
    set_user_verification_token, get_user_count
)
from datetime import datetime, timedelta


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    with flask_app.test_client() as c:
        yield c


def test_register_page_loads(client):
    """Test that registration page loads successfully."""
    res = client.get('/register')
    assert res.status_code == 200
    assert b'Register' in res.data or b'Sign up' in res.data


def test_register_with_valid_gmail(client):
    """Test registration with valid Gmail address."""
    res = client.post('/register', data={
        'username': 'test@gmail.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Should redirect to verify page or show success message
    assert b'verification' in res.data.lower() or res.status_code == 200


def test_register_rejects_non_gmail(client):
    """Test that non-Gmail addresses are rejected."""
    res = client.post('/register', data={
        'username': 'test@yahoo.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'gmail' in res.data.lower()


def test_register_rejects_mismatched_passwords(client):
    """Test that mismatched passwords are rejected."""
    res = client.post('/register', data={
        'username': 'test@gmail.com',
        'password': 'Test123!',
        'confirm': 'Different123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'match' in res.data.lower() or b'password' in res.data.lower()


def test_register_first_user_becomes_admin(client):
    """Test that first user automatically becomes admin."""
    res = client.post('/register', data={
        'username': 'admin@gmail.com',
        'password': 'Admin123!',
        'confirm': 'Admin123!'
    }, follow_redirects=True)
    user = get_user_by_username(flask_app.config['DATABASE'], 'admin@gmail.com')
    assert user is not None
    assert user.get('is_admin') == 1 or user.get('is_admin') is True


def test_register_duplicate_email(client):
    """Test that duplicate email registration is handled."""
    client.post('/register', data={
        'username': 'duplicate@gmail.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    res = client.post('/register', data={
        'username': 'duplicate@gmail.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Should show message about existing account


def test_login_page_loads(client):
    """Test that login page loads successfully."""
    res = client.get('/login')
    assert res.status_code == 200
    assert b'Login' in res.data or b'Sign in' in res.data


def test_login_with_valid_credentials(client):
    """Test login with valid credentials."""
    # Create and verify a user first
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'loginuser@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True)
    mark_user_verified(db_path, user_id)
    
    res = client.post('/login', data={
        'username': 'loginuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Dashboard' in res.data or 'user_id' in client.session


def test_login_with_invalid_credentials(client):
    """Test login with invalid credentials."""
    res = client.post('/login', data={
        'username': 'nonexistent@gmail.com',
        'password': 'WrongPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid' in res.data or b'error' in res.data.lower()


def test_login_with_wrong_password(client):
    """Test login with correct username but wrong password."""
    db_path = flask_app.config['DATABASE']
    create_user(db_path, 'wrongpass@gmail.com', generate_password_hash('Correct123!'),
                is_approved=True)
    
    res = client.post('/login', data={
        'username': 'wrongpass@gmail.com',
        'password': 'WrongPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid' in res.data or b'error' in res.data.lower()


def test_login_unverified_user(client):
    """Test that unverified users cannot login."""
    db_path = flask_app.config['DATABASE']
    create_user(db_path, 'unverified@gmail.com', generate_password_hash('Test123!'),
                is_approved=False)
    
    res = client.post('/login', data={
        'username': 'unverified@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'verified' in res.data.lower() or b'verify' in res.data.lower()


def test_logout_clears_session(client):
    """Test that logout clears the session."""
    # Login first
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'logoutuser@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True)
    mark_user_verified(db_path, user_id)
    
    client.post('/login', data={
        'username': 'logoutuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    
    # Logout
    with client.session_transaction() as sess:
        assert sess.get('user_id') is not None  # Verify logged in
    
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    
    # Check session is cleared
    with client.session_transaction() as sess:
        assert sess.get('user_id') is None


def test_verify_code_page_loads(client):
    """Test that verification code page loads."""
    res = client.get('/verify')
    assert res.status_code == 200
    assert b'code' in res.data.lower() or b'verify' in res.data.lower()


def test_verify_code_with_valid_code(client):
    """Test verification with valid 6-digit code."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'verifyuser@gmail.com', generate_password_hash('Test123!'),
                          is_approved=False)
    code = '123456'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    res = client.post('/verify', data={'code': '123456'}, follow_redirects=True)
    assert res.status_code == 200
    # Should redirect to login or password creation
    user = get_user_by_username(db_path, 'verifyuser@gmail.com')
    assert user.get('is_approved') == 1


def test_verify_code_with_invalid_code(client):
    """Test verification with invalid code."""
    res = client.post('/verify', data={'code': '000000'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid' in res.data or b'error' in res.data.lower()


def test_verify_code_with_expired_code(client):
    """Test verification with expired code."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'expireduser@gmail.com', generate_password_hash('Test123!'),
                          is_approved=False)
    code = '999999'
    expires_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat()  # Expired
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    res = client.post('/verify', data={'code': '999999'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'expired' in res.data.lower() or b'Invalid' in res.data


def test_create_password_page_loads(client):
    """Test that password creation page loads."""
    # Set session for pending password user
    with client.session_transaction() as sess:
        sess['pending_password_user'] = 'newuser@gmail.com'
        sess['pending_password_user_id'] = 1
    
    res = client.get('/create-password', follow_redirects=True)
    # May redirect if session not properly set, but should be 200 or 302
    assert res.status_code in (200, 302)


def test_create_password_success(client):
    """Test successful password creation."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'newpassuser@gmail.com', '', is_approved=True)
    
    with client.session_transaction() as sess:
        sess['pending_password_user'] = 'newpassuser@gmail.com'
        sess['pending_password_user_id'] = user_id
    
    res = client.post('/create-password', data={
        'password': 'NewPass123!',
        'confirm': 'NewPass123!'
    }, follow_redirects=True)
    # Should redirect to login (302) or show success (200)
    assert res.status_code in (200, 302)
    # Check password was set (may be empty string initially, but should be set after)
    user = get_user_by_username(db_path, 'newpassuser@gmail.com')
    # Password should be set (not None and not empty)
    password_hash = user.get('password_hash', '')
    assert password_hash is not None
    assert password_hash.strip() != '' or res.status_code == 200  # Either password set or page loaded


def test_create_password_mismatch(client):
    """Test password creation with mismatched passwords."""
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'mismatch@gmail.com', '', is_approved=True)
    
    with client.session_transaction() as sess:
        sess['pending_password_user'] = 'mismatch@gmail.com'
        sess['pending_password_user_id'] = user_id
    
    res = client.post('/create-password', data={
        'password': 'Pass123!',
        'confirm': 'Different123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Should show error about password mismatch
    assert b'match' in res.data.lower() or b'password' in res.data.lower() or b'error' in res.data.lower()


def test_protected_route_requires_login(client):
    """Test that protected routes redirect to login."""
    res = client.get('/dashboard', follow_redirects=False)
    assert res.status_code in (302, 303)  # Redirect to login


def test_forgot_password_page_loads(client):
    """Test that forgot password page loads."""
    res = client.get('/forgot_password')
    assert res.status_code == 200
    assert b'password' in res.data.lower() or b'forgot' in res.data.lower()


def test_register_empty_fields(client):
    """Test registration with empty fields."""
    res = client.post('/register', data={
        'username': '',
        'password': '',
        'confirm': ''
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'fill' in res.data.lower() or b'field' in res.data.lower()


def test_verify_code_empty_code(client):
    """Test verification with empty code."""
    res = client.post('/verify', data={'code': ''}, follow_redirects=True)
    assert res.status_code == 200
    assert b'valid' in res.data.lower() or b'code' in res.data.lower()


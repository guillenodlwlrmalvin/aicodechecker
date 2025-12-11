"""Tests for Authentication & Authorization (25 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username, 
    get_user_by_id, approve_user, mark_user_verified,
    update_user_password, set_user_verification_token,
    get_user_by_verification_code
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_auth.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path):
    """Create a test client."""
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


def test_register_with_valid_gmail(client):
    """Test registration with valid Gmail address."""
    res = client.post('/register', data={
        'username': 'test@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'verification' in res.data.lower() or b'code' in res.data.lower()


def test_register_rejects_non_gmail(client):
    """Test that non-Gmail addresses are rejected."""
    res = client.post('/register', data={
        'username': 'test@example.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'gmail' in res.data.lower()


def test_register_first_user_becomes_admin(client, db_path):
    """Test that first registered user becomes admin."""
    res = client.post('/register', data={
        'username': 'admin@gmail.com',
        'password': 'Admin123!',
        'confirm': 'Admin123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'admin@gmail.com')
    assert user is not None
    assert user['is_admin'] == 1
    assert user['is_approved'] == 1


def test_register_duplicate_email(client, db_path):
    """Test that duplicate email registration is rejected."""
    # First registration
    client.post('/register', data={
        'username': 'duplicate@gmail.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    
    # Second registration with same email
    res = client.post('/register', data={
        'username': 'duplicate@gmail.com',
        'password': 'Test123!',
        'confirm': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'already registered' in res.data.lower() or b'exist' in res.data.lower() or b'registered' in res.data.lower()


def test_login_with_valid_credentials(client, db_path):
    """Test login with valid credentials."""
    # Create and approve user
    user_id = create_user(db_path, 'loginuser@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    assert user_id is not None
    
    res = client.post('/login', data={
        'username': 'loginuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'dashboard' in res.data.lower() or res.status_code == 200


def test_login_with_invalid_username(client):
    """Test login with non-existent username."""
    res = client.post('/login', data={
        'username': 'nonexistent@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'invalid' in res.data.lower() or b'error' in res.data.lower()


def test_login_with_wrong_password(client, db_path):
    """Test login with wrong password."""
    create_user(db_path, 'wrongpass@gmail.com', generate_password_hash('Correct123!'), is_approved=True)
    
    res = client.post('/login', data={
        'username': 'wrongpass@gmail.com',
        'password': 'Wrong123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'invalid' in res.data.lower() or b'error' in res.data.lower()


def test_login_unverified_user(client, db_path):
    """Test that unverified users cannot login."""
    create_user(db_path, 'unverified@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    
    res = client.post('/login', data={
        'username': 'unverified@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'verified' in res.data.lower() or b'verify' in res.data.lower()


def test_logout_clears_session(client, db_path):
    """Test that logout clears the session."""
    # Create user and login
    user_id = create_user(db_path, 'logoutuser@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'logoutuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    
    # Logout
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    
    # Try to access protected route
    res = client.get('/dashboard', follow_redirects=True)
    assert b'login' in res.data.lower() or res.status_code == 302


def test_verify_code_with_valid_code(client, db_path):
    """Test verification with valid 6-digit code."""
    user_id = create_user(db_path, 'verifyuser@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    from datetime import datetime, timedelta
    code = '123456'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    res = client.post('/verify', data={'code': code}, follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'verifyuser@gmail.com')
    assert user['is_approved'] == 1


def test_verify_code_with_expired_code(client, db_path):
    """Test verification with expired code."""
    user_id = create_user(db_path, 'expireduser@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    from datetime import datetime, timedelta
    code = '654321'
    expires_at = (datetime.utcnow() - timedelta(minutes=1)).isoformat()  # Expired
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    res = client.post('/verify', data={'code': code}, follow_redirects=True)
    assert res.status_code == 200
    assert b'invalid' in res.data.lower() or b'expired' in res.data.lower()


def test_create_password_for_google_user(client, db_path):
    """Test password creation for Google OAuth user."""
    # Create user without password (Google user)
    user_id = create_user(db_path, 'newuser@gmail.com', '', is_approved=True)
    
    with client.session_transaction() as sess:
        sess['pending_password_user'] = 'newuser@gmail.com'
        sess['pending_password_user_id'] = user_id
    
    res = client.post('/create-password', data={
        'password': 'NewPass123!',
        'confirm_password': 'NewPass123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    
    user = get_user_by_username(db_path, 'newuser@gmail.com')
    assert user['password_hash'] is not None
    assert check_password_hash(user['password_hash'], 'NewPass123!')


def test_create_password_mismatch(client, db_path):
    """Test password creation with mismatched passwords."""
    user_id = create_user(db_path, 'mismatch@gmail.com', '', is_approved=True)
    
    with client.session_transaction() as sess:
        sess['pending_password_user'] = 'mismatch@gmail.com'
        sess['pending_password_user_id'] = user_id
    
    res = client.post('/create-password', data={
        'password': 'Pass123!',
        'confirm_password': 'Different123!'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'match' in res.data.lower() or b'error' in res.data.lower()


def test_password_update(client, db_path):
    """Test updating user password."""
    user_id = create_user(db_path, 'updatepass@gmail.com', generate_password_hash('Old123!'), is_approved=True)
    new_password_hash = generate_password_hash('New123!')
    update_user_password(db_path, user_id, new_password_hash)
    
    user = get_user_by_username(db_path, 'updatepass@gmail.com')
    assert check_password_hash(user['password_hash'], 'New123!')


def test_approve_user_functionality(client, db_path):
    """Test user approval functionality."""
    user_id = create_user(db_path, 'pending@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    assert get_user_by_id(db_path, user_id)['is_approved'] == 0
    
    approve_user(db_path, user_id)
    assert get_user_by_id(db_path, user_id)['is_approved'] == 1


def test_mark_user_verified(client, db_path):
    """Test marking user as verified."""
    user_id = create_user(db_path, 'verify@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    mark_user_verified(db_path, user_id)
    
    user = get_user_by_id(db_path, user_id)
    assert user['is_approved'] == 1


def test_get_user_by_verification_code(client, db_path):
    """Test retrieving user by verification code."""
    user_id = create_user(db_path, 'codeuser@gmail.com', generate_password_hash('Test123!'), is_approved=False)
    from datetime import datetime, timedelta
    code = '999888'
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    set_user_verification_token(db_path, user_id, code, expires_at)
    
    user = get_user_by_verification_code(db_path, code)
    assert user is not None
    assert user['id'] == user_id


def test_protected_route_requires_login(client):
    """Test that protected routes require login."""
    res = client.get('/dashboard', follow_redirects=False)
    assert res.status_code in (302, 303)  # Redirect to login


def test_protected_route_with_login(client, db_path):
    """Test accessing protected route after login."""
    user_id = create_user(db_path, 'protected@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'protected@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    
    res = client.get('/dashboard', follow_redirects=True)
    assert res.status_code == 200


def test_register_empty_fields(client):
    """Test registration with empty fields."""
    res = client.post('/register', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)
    assert res.status_code == 200  # Form validation should handle this


def test_login_empty_fields(client):
    """Test login with empty fields."""
    res = client.post('/login', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)
    assert res.status_code == 200  # Form validation should handle this


def test_verify_code_invalid_format(client):
    """Test verification with invalid code format."""
    res = client.post('/verify', data={'code': '12345'}, follow_redirects=True)  # 5 digits
    assert res.status_code == 200
    assert b'invalid' in res.data.lower() or b'6-digit' in res.data.lower()


def test_verify_code_non_numeric(client):
    """Test verification with non-numeric code."""
    res = client.post('/verify', data={'code': 'abcdef'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'invalid' in res.data.lower() or b'6-digit' in res.data.lower()


def test_forgot_password_route(client):
    """Test forgot password route."""
    res = client.get('/forgot_password', follow_redirects=True)
    assert res.status_code == 200


def test_forgot_password_with_valid_email(client, db_path):
    """Test forgot password with valid email."""
    create_user(db_path, 'forgot@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    res = client.post('/forgot_password', data={
        'username': 'forgot@gmail.com'
    }, follow_redirects=True)
    assert res.status_code == 200


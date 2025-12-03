"""
Unit tests for authentication and user management.
"""
import os
import tempfile
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import app as flask_app
from models import (
    initialize_database,
    create_user,
    get_user_by_username,
    get_user_count,
    approve_user,
    update_user_password,
    get_user_by_id,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_auth.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path, monkeypatch):
    """Create a test client with isolated database."""
    monkeypatch.setenv('FLASK_ENV', 'testing')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.config['MAIL_GMAIL_USER'] = None
    flask_app.config['MAIL_GMAIL_PASS'] = None
    
    with flask_app.test_client() as client:
        with flask_app.app_context():
            yield client


class TestUserRegistration:
    """Tests for user registration."""
    
    def test_register_page_loads(self, client):
        """Test that registration page loads."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'sign up' in response.data.lower()
    
    def test_register_first_user_becomes_admin(self, client, db_path):
        """Test that first user becomes admin automatically."""
        response = client.post('/register', data={
            'username': 'admin@test.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        user = get_user_by_username(db_path, 'admin@test.com')
        assert user is not None
        assert user['is_admin'] == 1
        assert user['is_approved'] == 1
    
    def test_register_second_user_not_admin(self, client, db_path):
        """Test that second user is not admin."""
        # Create first user (admin)
        create_user(db_path, 'admin@test.com', generate_password_hash('pass'), is_admin=True, is_approved=True)
        
        # Register second user
        response = client.post('/register', data={
            'username': 'user@test.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        user = get_user_by_username(db_path, 'user@test.com')
        assert user is not None
        assert user['is_admin'] == 0
        assert user['is_approved'] == 0
    
    def test_register_missing_fields(self, client):
        """Test registration with missing fields."""
        response = client.post('/register', data={
            'username': '',
            'password': 'password123'
        })
        assert response.status_code == 200
        # Should show error message
    
    def test_register_duplicate_username(self, client, db_path):
        """Test registration with duplicate username."""
        create_user(db_path, 'test@test.com', generate_password_hash('pass'))
        
        response = client.post('/register', data={
            'username': 'test@test.com',
            'password': 'password123'
        })
        assert response.status_code == 200
        # Should handle duplicate gracefully


class TestUserLogin:
    """Tests for user login."""
    
    def test_login_page_loads(self, client):
        """Test that login page loads."""
        response = client.get('/login')
        assert response.status_code == 200
    
    def test_login_success(self, client, db_path):
        """Test successful login."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'test@test.com', password_hash, is_approved=1)
        
        response = client.post('/login', data={
            'username': 'test@test.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Check session
        with client.session_transaction() as sess:
            assert sess.get('user_id') == 'test@test.com'
    
    def test_login_invalid_credentials(self, client, db_path):
        """Test login with invalid credentials."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'test@test.com', password_hash, is_approved=1)
        
        response = client.post('/login', data={
            'username': 'test@test.com',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get('user_id') is None
    
    def test_login_unapproved_user(self, client, db_path):
        """Test login with unapproved user."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'test@test.com', password_hash, is_approved=0)
        
        response = client.post('/login', data={
            'username': 'test@test.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show approval pending message
        with client.session_transaction() as sess:
            assert sess.get('user_id') is None
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post('/login', data={
            'username': 'nonexistent@test.com',
            'password': 'password123'
        })
        
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess.get('user_id') is None


class TestUserLogout:
    """Tests for user logout."""
    
    def test_logout(self, client, db_path):
        """Test logout functionality."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'test@test.com', password_hash, is_approved=1)
        
        # Login first
        client.post('/login', data={
            'username': 'test@test.com',
            'password': 'password123'
        })
        
        # Logout
        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
        
        with client.session_transaction() as sess:
            assert sess.get('user_id') is None


class TestDatabaseOperations:
    """Tests for database operations."""
    
    def test_create_user(self, db_path):
        """Test user creation."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        assert user_id > 0
        
        user = get_user_by_username(db_path, 'test@test.com')
        assert user is not None
        assert user['username'] == 'test@test.com'
        assert user['password_hash'] == 'hash123'
    
    def test_get_user_by_username(self, db_path):
        """Test getting user by username."""
        create_user(db_path, 'test@test.com', 'hash123')
        
        user = get_user_by_username(db_path, 'test@test.com')
        assert user is not None
        assert user['username'] == 'test@test.com'
        
        # Non-existent user
        user = get_user_by_username(db_path, 'nonexistent@test.com')
        assert user is None
    
    def test_get_user_by_id(self, db_path):
        """Test getting user by ID."""
        user_id = create_user(db_path, 'test@test.com', 'hash123')
        
        user = get_user_by_id(db_path, user_id)
        assert user is not None
        assert user['id'] == user_id
        assert user['username'] == 'test@test.com'
    
    def test_approve_user(self, db_path):
        """Test user approval."""
        user_id = create_user(db_path, 'test@test.com', 'hash123', is_approved=0)
        
        approve_user(db_path, user_id)
        
        user = get_user_by_id(db_path, user_id)
        assert user['is_approved'] == 1
    
    def test_update_user_password(self, db_path):
        """Test password update."""
        user_id = create_user(db_path, 'test@test.com', 'old_hash')
        
        new_hash = generate_password_hash('newpassword123')
        update_user_password(db_path, user_id, new_hash)
        
        user = get_user_by_id(db_path, user_id)
        assert check_password_hash(user['password_hash'], 'newpassword123')
    
    def test_get_user_count(self, db_path):
        """Test getting user count."""
        assert get_user_count(db_path) == 0
        
        create_user(db_path, 'user1@test.com', 'hash1')
        assert get_user_count(db_path) == 1
        
        create_user(db_path, 'user2@test.com', 'hash2')
        assert get_user_count(db_path) == 2


class TestProtectedRoutes:
    """Tests for protected routes requiring authentication."""
    
    def test_dashboard_requires_login(self, client):
        """Test that dashboard requires login."""
        response = client.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to login
    
    def test_dashboard_with_login(self, client, db_path):
        """Test dashboard access with login."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'test@test.com', password_hash, is_approved=1)
        
        # Login
        client.post('/login', data={
            'username': 'test@test.com',
            'password': 'password123'
        })
        
        # Access dashboard
        response = client.get('/dashboard', follow_redirects=True)
        assert response.status_code == 200
    
    def test_admin_requires_admin_role(self, client, db_path):
        """Test that admin routes require admin role."""
        password_hash = generate_password_hash('password123')
        create_user(db_path, 'user@test.com', password_hash, is_approved=1, is_admin=0)
        
        # Login as non-admin
        client.post('/login', data={
            'username': 'user@test.com',
            'password': 'password123'
        })
        
        # Try to access admin page
        response = client.get('/admin', follow_redirects=True)
        assert response.status_code == 200
        # Should redirect or show error


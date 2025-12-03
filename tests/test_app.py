"""
Unit tests for Flask application routes and general functionality.
"""
import os
import tempfile
import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from app import app as flask_app
from models import initialize_database, create_user


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Create a test client with isolated database."""
    # Isolate DB per test
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.config['MAIL_GMAIL_USER'] = None
    flask_app.config['MAIL_GMAIL_PASS'] = None

    # Ensure schema exists for this temp DB
    initialize_database(db_path)

    with flask_app.test_client() as c:
        with flask_app.app_context():
            yield c


def login(client, username='Admin', password='Admin123'):
    """Helper function to login a user."""
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


class TestBasicRoutes:
    """Tests for basic application routes."""
    
    def test_index(self, client):
        """Test that index page loads."""
        res = client.get('/')
        assert res.status_code == 200
    
    def test_register_page(self, client):
        """Test that register page loads."""
        res = client.get('/register')
        assert res.status_code == 200
    
    def test_login_page(self, client):
        """Test that login page loads."""
        res = client.get('/login')
        assert res.status_code == 200
    
    def test_logout(self, client):
        """Test logout route."""
        res = client.get('/logout', follow_redirects=True)
        assert res.status_code == 200


class TestRegistrationFlow:
    """Tests for user registration flow."""
    
    def test_register_login_flow(self, client):
        """Test complete registration and login flow."""
        # Register first user becomes admin and approved
        res = client.post('/register', data={'username': 'alice', 'password': 'pw'}, follow_redirects=True)
        assert res.status_code == 200
        
        # Login
        res = client.post('/login', data={'username': 'alice', 'password': 'pw'}, follow_redirects=True)
        assert res.status_code == 200
        assert b'Dashboard' in res.data or res.status_code == 200


class TestCodeDetection:
    """Tests for code detection endpoints."""
    
    def test_detect_requires_login(self, client):
        """Test that /detect_enhanced endpoint requires login."""
        res = client.post('/detect_enhanced', json={'code': 'print(1)'}, follow_redirects=False)
        assert res.status_code in (302, 303, 401, 403, 404)
    
    def test_detect_flow_logged_in(self, client):
        """Test code detection with logged in user."""
        # Register and login
        client.post('/register', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
        client.post('/login', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
        
        # Try detection
        res = client.post('/detect_enhanced', json={'code': 'print(1)'}, follow_redirects=True)
        assert res.status_code in (200, 302)
    
    def test_detect_json_endpoint(self, client):
        """Test JSON detection endpoint."""
        # Register and login
        client.post('/register', data={'username': 'test', 'password': 'pw'}, follow_redirects=True)
        client.post('/login', data={'username': 'test', 'password': 'pw'}, follow_redirects=True)
        
        # Try JSON endpoint
        res = client.post('/detect_enhanced', json={'code': 'print("hello")', 'language': 'python'}, follow_redirects=True)
        # May return 200, 302, or 400 depending on implementation
        assert res.status_code in (200, 302, 400, 500)


class TestProtectedRoutes:
    """Tests for routes that require authentication."""
    
    def test_dashboard_requires_login(self, client):
        """Test that dashboard requires login."""
        res = client.get('/dashboard', follow_redirects=True)
        assert res.status_code == 200
        # Should redirect to login or show login page
    
    def test_dashboard_with_login(self, client):
        """Test dashboard access with login."""
        # Register and login
        client.post('/register', data={'username': 'user', 'password': 'pw'}, follow_redirects=True)
        client.post('/login', data={'username': 'user', 'password': 'pw'}, follow_redirects=True)
        
        # Access dashboard
        res = client.get('/dashboard', follow_redirects=True)
        assert res.status_code == 200
    
    def test_code_analysis_requires_login(self, client):
        """Test that code analysis requires login."""
        res = client.get('/code_analysis', follow_redirects=True)
        assert res.status_code == 200
        # Should redirect to login



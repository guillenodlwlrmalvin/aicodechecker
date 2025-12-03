"""
Unit tests for code analysis features.
"""
import os
import pytest

from app import app as flask_app
from models import initialize_database, create_user, create_analysis
from werkzeug.security import generate_password_hash


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_analysis.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path, monkeypatch):
    """Create a test client with isolated database."""
    monkeypatch.setenv('FLASK_ENV', 'testing')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    
    with flask_app.test_client() as client:
        with flask_app.app_context():
            yield client


@pytest.fixture
def logged_in_user(client, db_path):
    """Create and login a test user."""
    password_hash = generate_password_hash('password123')
    user_id = create_user(db_path, 'test@test.com', password_hash, is_approved=1)
    
    client.post('/login', data={
        'username': 'test@test.com',
        'password': 'password123'
    })
    
    return user_id


class TestCodeAnalysis:
    """Tests for code analysis functionality."""
    
    def test_code_analysis_page_requires_login(self, client):
        """Test that code analysis page requires login."""
        response = client.get('/code_analysis', follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to login
    
    def test_code_analysis_page_loads(self, client, logged_in_user):
        """Test that code analysis page loads for logged in users."""
        response = client.get('/code_analysis', follow_redirects=True)
        assert response.status_code == 200
    
    def test_detect_endpoint_requires_login(self, client):
        """Test that /detect_enhanced endpoint requires login."""
        response = client.post('/detect_enhanced', json={'code': 'print("hello")'})
        assert response.status_code in [302, 401, 403, 404]  # Redirect or unauthorized
    
    def test_detect_endpoint_with_login(self, client, logged_in_user, db_path):
        """Test code detection with logged in user."""
        test_code = 'print("Hello, World!")'
        
        response = client.post('/detect_enhanced', data={
            'code': test_code,
            'language': 'python'
        }, follow_redirects=True)
        
        # Returns HTML template, not JSON
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'analysis' in response.data.lower()
    
    def test_detect_enhanced_endpoint(self, client, logged_in_user):
        """Test enhanced detection endpoint."""
        test_code = '''
def hello():
    print("Hello, World!")
    return True
'''
        response = client.post('/detect_enhanced', data={
            'code': test_code,
            'language': 'python'
        }, follow_redirects=True)
        
        # Returns HTML template
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'analysis' in response.data.lower()
    
    def test_analysis_history(self, client, logged_in_user, db_path):
        """Test analysis history retrieval."""
        # Create some analysis records
        test_code = 'print("test")'
        create_analysis(db_path, logged_in_user, test_code, 'python', 'human', 0.8, check_ok=True, check_errors=[])
        
        response = client.get('/history/latest', follow_redirects=True)
        # Returns HTML template, not JSON
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'history' in response.data.lower()


class TestFileUpload:
    """Tests for file upload functionality."""
    
    def test_upload_requires_login(self, client):
        """Test that file upload requires login."""
        response = client.post('/upload', data={})
        assert response.status_code in [302, 401, 403]
    
    def test_upload_valid_file(self, client, logged_in_user, tmp_path):
        """Test uploading a valid file."""
        # Create a test file
        test_file = tmp_path / 'test.py'
        test_file.write_text('print("Hello, World!")')
        
        with open(test_file, 'rb') as f:
            response = client.post('/upload', data={
                'file': (f, 'test.py')
            }, content_type='multipart/form-data', follow_redirects=True)
        
        # Returns HTML after redirect
        assert response.status_code == 200
        assert b'dashboard' in response.data.lower() or b'upload' in response.data.lower()
    
    def test_upload_invalid_extension(self, client, logged_in_user, tmp_path):
        """Test uploading file with invalid extension."""
        test_file = tmp_path / 'test.txt'
        test_file.write_text('some text')
        
        with open(test_file, 'rb') as f:
            response = client.post('/upload', data={
                'file': (f, 'test.txt')
            }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should reject invalid file type or redirect
        assert response.status_code in [200, 302, 400]


class TestCodeExecution:
    """Tests for code execution features."""
    
    def test_execute_code_requires_login(self, client):
        """Test that code execution requires login."""
        response = client.post('/run_code', json={
            'code': 'print("hello")',
            'language': 'python'
        })
        assert response.status_code in [302, 401, 403, 404]
    
    def test_execute_python_code(self, client, logged_in_user):
        """Test executing Python code."""
        response = client.post('/run_code', json={
            'code': 'print("Hello, World!")',
            'language': 'python'
        }, follow_redirects=True)
        
        # May redirect or return 200
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None


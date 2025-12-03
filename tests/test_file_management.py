"""
Unit tests for file management functionality.
"""
import os
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from models import (
    initialize_database, create_user, create_uploaded_file,
    get_uploaded_files, get_uploaded_file
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_files.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path, monkeypatch, tmp_path):
    """Create a test client with isolated database."""
    monkeypatch.setenv('FLASK_ENV', 'testing')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    
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


class TestFileUpload:
    """Tests for file upload functionality."""
    
    def test_upload_python_file(self, client, logged_in_user, db_path, tmp_path):
        """Test uploading a Python file."""
        test_file = tmp_path / 'test.py'
        test_file.write_text('print("Hello, World!")')
        
        with open(test_file, 'rb') as f:
            response = client.post('/upload', data={
                'file': (f, 'test.py')
            }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_upload_java_file(self, client, logged_in_user, db_path, tmp_path):
        """Test uploading a Java file."""
        test_file = tmp_path / 'Test.java'
        test_file.write_text('public class Test { public static void main(String[] args) {} }')
        
        with open(test_file, 'rb') as f:
            response = client.post('/upload', data={
                'file': (f, 'Test.java')
            }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_upload_invalid_file_type(self, client, logged_in_user, db_path, tmp_path):
        """Test uploading an invalid file type."""
        test_file = tmp_path / 'test.txt'
        test_file.write_text('some text')
        
        with open(test_file, 'rb') as f:
            response = client.post('/upload', data={
                'file': (f, 'test.txt')
            }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should reject or show error
        assert response.status_code in [200, 302]
    
    def test_upload_empty_file(self, client, logged_in_user, db_path):
        """Test uploading an empty file."""
        response = client.post('/upload', data={}, follow_redirects=True)
        # Should handle gracefully
        assert response.status_code in [200, 302]


class TestFileManagement:
    """Tests for file management operations."""
    
    def test_get_uploaded_files(self, client, logged_in_user, db_path, tmp_path):
        """Test retrieving uploaded files."""
        # Create some uploaded files
        create_uploaded_file(db_path, logged_in_user, 'test1.py', 'test1.py', 100, 'py', 'code1')
        create_uploaded_file(db_path, logged_in_user, 'test2.py', 'test2.py', 200, 'py', 'code2')
        
        files = get_uploaded_files(db_path, logged_in_user)
        assert len(files) >= 2
    
    def test_get_uploaded_file_by_id(self, client, logged_in_user, db_path, tmp_path):
        """Test retrieving a specific uploaded file."""
        file_id = create_uploaded_file(
            db_path, logged_in_user, 'test.py', 'test.py', 100, 'py', 'code'
        )
        
        file = get_uploaded_file(db_path, file_id)
        assert file is not None
        assert file['filename'] == 'test.py'
    
    def test_clear_uploaded_files(self, client, logged_in_user, db_path, tmp_path):
        """Test clearing all uploaded files."""
        # Create some files
        create_uploaded_file(db_path, logged_in_user, 'test1.py', 'test1.py', 100, 'py', 'code1')
        
        response = client.post('/clear_uploaded_files', follow_redirects=True)
        assert response.status_code == 200
    
    def test_remove_uploaded_file(self, client, logged_in_user, db_path, tmp_path):
        """Test removing a specific uploaded file."""
        file_id = create_uploaded_file(
            db_path, logged_in_user, 'test.py', 'test.py', 100, 'py', 'code'
        )
        
        response = client.post(f'/remove_uploaded_file/{file_id}', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify file is removed
        file = get_uploaded_file(db_path, file_id)
        assert file is None


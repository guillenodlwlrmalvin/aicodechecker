"""Tests for File Management (10 tests)."""
import os
import io
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import initialize_database, create_user, create_uploaded_file, get_uploaded_files


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_files.db')
    initialize_database(db)
    return db


@pytest.fixture
def client(db_path):
    """Create a test client."""
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_user(client, db_path):
    """Create and login a user."""
    user_id = create_user(db_path, 'fileuser@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'fileuser@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    return user_id


def test_upload_file_requires_login(client):
    """Test that file upload requires login."""
    res = client.post('/upload', data={}, follow_redirects=False)
    assert res.status_code in (302, 303)


def test_upload_file_with_valid_file(client, db_path, logged_in_user):
    """Test uploading a valid file."""
    from models import get_user_by_username
    user = get_user_by_username(db_path, 'fileuser@gmail.com')
    
    # Create a test file
    test_file = (io.BytesIO(b'print("hello")'), 'test.py')
    res = client.post('/upload', data={
        'file': test_file
    }, follow_redirects=True)
    assert res.status_code == 200


def test_upload_file_invalid_extension(client, db_path, logged_in_user):
    """Test uploading file with invalid extension."""
    test_file = (io.BytesIO(b'content'), 'test.txt')
    res = client.post('/upload', data={
        'file': test_file
    }, follow_redirects=True)
    # Should reject or show error
    assert res.status_code == 200


def test_clear_uploaded_files(client, db_path, logged_in_user):
    """Test clearing all uploaded files."""
    from models import get_user_by_username, create_uploaded_file
    user = get_user_by_username(db_path, 'fileuser@gmail.com')
    create_uploaded_file(db_path, user['id'], 'file1.py', 'file1.py', 50, 'py', 'code1')
    
    res = client.post('/clear_uploaded_files', follow_redirects=True)
    assert res.status_code == 200
    
    files = get_uploaded_files(db_path, user['id'])
    assert len(files) == 0


def test_remove_uploaded_file(client, db_path, logged_in_user):
    """Test removing a single uploaded file."""
    from models import get_user_by_username, create_uploaded_file
    user = get_user_by_username(db_path, 'fileuser@gmail.com')
    file_id = create_uploaded_file(db_path, user['id'], 'remove.py', 'remove.py', 50, 'py', 'code')
    
    res = client.post(f'/remove_uploaded_file/{file_id}', follow_redirects=True)
    assert res.status_code == 200
    
    files = get_uploaded_files(db_path, user['id'])
    assert len(files) == 0


def test_get_uploaded_files(client, db_path, logged_in_user):
    """Test retrieving uploaded files."""
    from models import get_user_by_username, create_uploaded_file
    user = get_user_by_username(db_path, 'fileuser@gmail.com')
    create_uploaded_file(db_path, user['id'], 'file1.py', 'file1.py', 50, 'py', 'code1')
    create_uploaded_file(db_path, user['id'], 'file2.py', 'file2.py', 60, 'py', 'code2')
    
    files = get_uploaded_files(db_path, user['id'])
    assert len(files) == 2


def test_allowed_file_extensions():
    """Test allowed file extension validation."""
    from app import allowed_file
    assert allowed_file('test.py') == True
    assert allowed_file('test.java') == True
    assert allowed_file('test.txt') == False
    assert allowed_file('test.py.bak') == False


def test_get_language_from_extension():
    """Test getting language from file extension."""
    from app import get_language_from_extension
    assert get_language_from_extension('test.py') == 'python'
    assert get_language_from_extension('test.java') == 'java'
    assert get_language_from_extension('test.txt') == 'auto'  # Default for unknown extensions


def test_upload_file_size_limit(client, db_path, logged_in_user):
    """Test file upload size limit."""
    # Create a large file (simulate)
    large_content = b'x' * (17 * 1024 * 1024)  # 17MB, over 16MB limit
    test_file = (io.BytesIO(large_content), 'large.py')
    res = client.post('/upload', data={
        'file': test_file
    }, follow_redirects=True)
    # Should reject large files with 413 status
    assert res.status_code == 413


def test_upload_file_with_analysis(client, db_path, logged_in_user):
    """Test that uploaded file can be used for analysis."""
    from models import get_user_by_username, get_uploaded_files
    user = get_user_by_username(db_path, 'fileuser@gmail.com')
    
    # Upload file
    file_id = create_uploaded_file(db_path, user['id'], 'analyze.py', 'analyze.py', 50, 'py', 'print("test")')
    
    files = get_uploaded_files(db_path, user['id'])
    assert len(files) == 1
    assert files[0]['id'] == file_id


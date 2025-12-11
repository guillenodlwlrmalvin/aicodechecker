"""Tests for Code Analysis (8 tests)."""
import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import initialize_database, create_user, create_analysis


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db = os.path.join(tmp_path, 'test_analysis.db')
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
    user_id = create_user(db_path, 'analyst@gmail.com', generate_password_hash('Test123!'), is_approved=True)
    client.post('/login', data={
        'username': 'analyst@gmail.com',
        'password': 'Test123!'
    }, follow_redirects=True)
    return user_id


def test_detect_enhanced_endpoint_requires_login(client):
    """Test that detect_enhanced endpoint requires login."""
    res = client.post('/detect_enhanced', data={'code': 'print(1)'}, follow_redirects=False)
    assert res.status_code in (302, 303)  # Redirect to login


def test_detect_enhanced_with_code(client, logged_in_user):
    """Test detect_enhanced endpoint with code."""
    res = client.post('/detect_enhanced', data={
        'code': 'print("hello world")',
        'language': 'python'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_detect_enhanced_creates_analysis(client, db_path, logged_in_user):
    """Test that detect_enhanced creates an analysis record."""
    from models import get_recent_analyses, get_user_by_username
    
    user = get_user_by_username(db_path, 'analyst@gmail.com')
    initial_count = len(get_recent_analyses(db_path, user['id']))
    
    client.post('/detect_enhanced', data={
        'code': 'x = 1 + 2',
        'language': 'python'
    }, follow_redirects=True)
    
    final_count = len(get_recent_analyses(db_path, user['id']))
    assert final_count > initial_count


def test_code_analysis_page_requires_login(client):
    """Test that code analysis page requires login."""
    res = client.get('/code_analysis', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_code_analysis_page_with_login(client, logged_in_user):
    """Test accessing code analysis page when logged in."""
    res = client.get('/code_analysis', follow_redirects=True)
    assert res.status_code == 200


def test_history_latest_requires_login(client):
    """Test that history/latest requires login."""
    res = client.get('/history/latest', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_history_view_requires_login(client):
    """Test that history view requires login."""
    res = client.get('/history/1', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_history_view_with_valid_id(client, db_path, logged_in_user):
    """Test viewing history with valid analysis ID."""
    from models import get_user_by_username, get_recent_analyses
    
    user = get_user_by_username(db_path, 'analyst@gmail.com')
    analysis_id = create_analysis(
        db_path, user['id'], 'test code', 'python', 
        'Human', 0.5, True, []
    )
    
    res = client.get(f'/history/{analysis_id}', follow_redirects=True)
    assert res.status_code == 200


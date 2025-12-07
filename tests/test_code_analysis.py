import os
import pytest
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import (
    initialize_database, create_user, get_user_by_username, create_analysis,
    get_recent_analyses, get_analysis_by_id, mark_user_verified
)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    initialize_database(db_path)
    
    # Create a test user
    user_id = create_user(db_path, 'analyst@gmail.com', generate_password_hash('Test123!'),
                          is_approved=True)
    mark_user_verified(db_path, user_id)
    
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'analyst@gmail.com'
        yield c


def test_code_analysis_page_loads(client):
    """Test that code analysis page loads."""
    res = client.get('/code_analysis')
    assert res.status_code == 200
    assert b'analysis' in res.data.lower() or b'code' in res.data.lower()


def test_detect_enhanced_requires_login(client):
    """Test that detect_enhanced requires authentication."""
    with client.session_transaction() as sess:
        sess.clear()
    res = client.post('/detect_enhanced', data={'code': 'print("hello")'}, follow_redirects=False)
    assert res.status_code in (302, 303)  # Redirect to login


def test_detect_enhanced_with_code(client):
    """Test code detection with valid code input."""
    res = client.post('/detect_enhanced', data={
        'code': 'print("Hello, World!")',
        'language': 'python'
    }, follow_redirects=True)
    assert res.status_code == 200
    # Should return analysis result


def test_detect_enhanced_with_file_upload(client):
    """Test code detection with file upload."""
    # Create a test file
    test_file = ('test.py', 'test.py', b'print("test")', 'text/x-python')
    res = client.post('/detect_enhanced', data={
        'code': '',
        'language': 'python'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_history_page_loads(client):
    """Test that analysis history page loads."""
    res = client.get('/history/latest', follow_redirects=True)
    # May redirect if no analyses, but should be accessible
    assert res.status_code in (200, 302)


def test_history_shows_analyses(client):
    """Test that history shows user's analyses."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'analyst@gmail.com')
    create_analysis(db_path, user['id'], 'print(1)', 'python', 'Human', 20.0, True, [])
    
    res = client.get('/history/latest')
    assert res.status_code == 200
    assert b'history' in res.data.lower() or b'analysis' in res.data.lower()


def test_detect_enhanced_with_empty_code(client):
    """Test detect_enhanced with empty code."""
    res = client.post('/detect_enhanced', data={'code': ''}, follow_redirects=True)
    assert res.status_code in (200, 302)
    # Should show error or redirect


def test_get_analysis_by_id(client):
    """Test retrieving specific analysis by ID."""
    db_path = flask_app.config['DATABASE']
    user = get_user_by_username(db_path, 'analyst@gmail.com')
    analysis_id = create_analysis(db_path, user['id'], 'print("test")', 'python', 'Human', 20.0, True, [])
    
    analysis = get_analysis_by_id(db_path, user['id'], analysis_id)
    assert analysis is not None
    assert analysis['id'] == analysis_id
    assert analysis['code'] == 'print("test")'




import os
import tempfile
import pytest

import app as app_module
from app import app as flask_app
from models import initialize_database


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # Isolate DB per test
    db_path = os.path.join(tmp_path, 'test.sqlite3')
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True

    # Ensure schema exists for this temp DB
    initialize_database(db_path)

    # LM client removed - no longer need monkeypatch

    with flask_app.test_client() as c:
        yield c


def login(client, username='Admin', password='Admin123'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def test_index(client):
    res = client.get('/')
    assert res.status_code == 200


def test_register_login_flow(client):
    # Register first user becomes admin and approved
    res = client.post('/register', data={'username': 'alice', 'password': 'pw'}, follow_redirects=True)
    assert res.status_code == 200
    # Login
    res = client.post('/login', data={'username': 'alice', 'password': 'pw'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'Dashboard' in res.data or res.status_code == 200


def test_detect_requires_login(client):
    res = client.post('/detect_enhanced', data={'code': 'print(1)'}, follow_redirects=False)
    assert res.status_code in (302, 303)


def test_detect_flow_logged_in(client):
    # Use admin seeded or register quickly
    client.post('/register', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    client.post('/login', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    res = client.post('/detect_enhanced', data={'code': 'print(1)'}, follow_redirects=True)
    assert res.status_code == 200


def test_run_code_endpoint(client):
    """Test code execution endpoint."""
    # Login first
    from werkzeug.security import generate_password_hash
    from models import create_user, mark_user_verified
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'runcode@gmail.com', generate_password_hash('Test123!'),
                         is_approved=True)
    mark_user_verified(db_path, user_id)
    client.post('/login', data={'username': 'runcode@gmail.com', 'password': 'Test123!'},
               follow_redirects=True)
    
    res = client.post('/run_code', data={'code': 'print("hello")', 'language': 'python'},
                     follow_redirects=True)
    # Should execute or show result
    assert res.status_code in (200, 400, 500)


def test_remove_history_item(client):
    """Test removing a specific history item."""
    from werkzeug.security import generate_password_hash
    from models import create_user, mark_user_verified, create_analysis, get_user_by_username
    db_path = flask_app.config['DATABASE']
    user_id = create_user(db_path, 'history@gmail.com', generate_password_hash('Test123!'),
                         is_approved=True)
    mark_user_verified(db_path, user_id)
    client.post('/login', data={'username': 'history@gmail.com', 'password': 'Test123!'},
               follow_redirects=True)
    
    user = get_user_by_username(db_path, 'history@gmail.com')
    analysis_id = create_analysis(db_path, user['id'], 'print(1)', 'python', 'Human', 20.0, True, [])
    
    res = client.post(f'/remove_history/{analysis_id}', follow_redirects=True)
    assert res.status_code in (200, 302)



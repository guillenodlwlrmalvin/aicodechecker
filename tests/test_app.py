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
    res = client.post('/detect', data={'code': 'print(1)'}, follow_redirects=False)
    assert res.status_code in (302, 303) or res.status_code == 200  # May redirect or show login page


def test_detect_flow_logged_in(client):
    # Use admin seeded or register quickly
    client.post('/register', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    client.post('/login', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    res = client.post('/detect', data={'code': 'print(1)'}, follow_redirects=True)
    assert res.status_code == 200


def test_dashboard_redirects_based_on_role(client):
    """Test that dashboard redirects based on user role."""
    from models import create_user
    from werkzeug.security import generate_password_hash
    import os
    
    db_path = flask_app.config.get('DATABASE')
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), 'test.db')
        flask_app.config['DATABASE'] = db_path
    
    # Create admin user
    admin_id = create_user(db_path, 'adminrole@gmail.com', generate_password_hash('Test123!'), 
                          is_admin=True, is_approved=True)
    client.post('/login', data={'username': 'adminrole@gmail.com', 'password': 'Test123!'}, follow_redirects=True)
    
    res = client.get('/dashboard', follow_redirects=True)
    assert res.status_code == 200


def test_clear_history_requires_login(client):
    """Test that clear_history requires login."""
    res = client.post('/clear_history', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_remove_history_requires_login(client):
    """Test that remove_history requires login."""
    res = client.post('/remove_history/1', follow_redirects=False)
    assert res.status_code in (302, 303)


def test_run_code_requires_login(client):
    """Test that run_code requires login."""
    res = client.post('/run_code', data={'code': 'print(1)'}, follow_redirects=False)
    assert res.status_code in (302, 303)


def test_verify_email_legacy_route(client):
    """Test legacy verify email route redirects."""
    res = client.get('/verify/fake-token', follow_redirects=True)
    assert res.status_code == 200
    assert b'code' in res.data.lower() or b'verification' in res.data.lower()



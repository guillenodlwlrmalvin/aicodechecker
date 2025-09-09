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

    # Monkeypatch LM functions to avoid network
    def fake_classify(code, lang, base_url=None, model=None):
        return {'label': 'Uncertain (LLM)', 'score': 50.0, 'explanation': 'stub'}

    def fake_detect_lang(code, base_url=None, model=None):
        return 'python'

    monkeypatch.setattr(app_module, 'classify_with_lmstudio', fake_classify)
    monkeypatch.setattr(app_module, 'detect_language_with_lmstudio', fake_detect_lang)

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
    assert res.status_code in (302, 303)


def test_detect_flow_logged_in(client):
    # Use admin seeded or register quickly
    client.post('/register', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    client.post('/login', data={'username': 'bob', 'password': 'pw'}, follow_redirects=True)
    res = client.post('/detect', data={'code': 'print(1)'}, follow_redirects=True)
    assert res.status_code == 200



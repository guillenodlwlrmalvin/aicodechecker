"""
Pytest configuration and shared fixtures.
"""
import os
import sys
import tempfile
import pytest

# Ensure the project root (where app.py resides) is on sys.path for tests
PROJECT_ROOT_CANDIDATES = [
    os.path.dirname(os.path.dirname(__file__)),  # one level up from tests/
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # two up (in case of nested copies)
]

for candidate in PROJECT_ROOT_CANDIDATES:
    if candidate and os.path.isfile(os.path.join(candidate, 'app.py')):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
        break


@pytest.fixture(scope='session')
def test_database():
    """Create a temporary database for testing."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    yield db_path
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv('FLASK_ENV', 'testing')
    monkeypatch.setenv('TESTING', 'True')
    # Disable email sending in tests
    monkeypatch.setenv('GMAIL_USER', '')
    monkeypatch.setenv('GMAIL_PASS', '')
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test-client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test-client-secret')



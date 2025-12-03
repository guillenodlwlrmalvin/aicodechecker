# Testing Guide for CodeCraft

This document provides information about the unit test suite for the CodeCraft Flask application.

## Test Suite Overview

The test suite is organized into several modules:

### Test Files

1. **`test_auth.py`** - Authentication and user management
   - User registration (first user becomes admin)
   - User login/logout
   - Password management
   - User approval workflow
   - Protected routes

2. **`test_models.py`** - Database operations
   - User CRUD operations
   - Analysis records
   - Groups and activities
   - Submissions

3. **`test_code_analysis.py`** - Code analysis features
   - Code detection endpoints
   - File uploads
   - Analysis history
   - Code execution

4. **`test_utils.py`** - Utility functions
   - Password hashing
   - Code validation
   - Email validation

5. **`test_app.py`** - General application routes
   - Basic route accessibility
   - Registration/login flow
   - Code detection flow

## Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test class
pytest tests/test_auth.py::TestUserRegistration

# Run specific test
pytest tests/test_auth.py::TestUserRegistration::test_register_first_user_becomes_admin
```

### Using the Test Runner Script

```bash
python run_tests.py
```

### With Coverage Report

```bash
# Install coverage tool
pip install pytest-cov

# Run tests with coverage
pytest --cov=. --cov-report=html

# View HTML report
# Open htmlcov/index.html in your browser
```

## Test Fixtures

### Database Fixtures

- `db_path` - Creates a temporary database for each test
- `client` - Flask test client with isolated database
- `logged_in_user` - Pre-authenticated test user fixture

### Example Usage

```python
def test_something(client, db_path):
    # client is a Flask test client
    # db_path is a temporary database path
    response = client.get('/some-route')
    assert response.status_code == 200
```

## Test Coverage

### Currently Tested Features

✅ **Authentication**
- User registration
- User login/logout
- Password verification
- User approval

✅ **Database Operations**
- User creation and retrieval
- Password updates
- Role management
- Analysis records
- Groups and activities

✅ **Code Analysis**
- Code detection endpoints
- File upload validation
- Analysis history

✅ **Route Protection**
- Login requirements
- Role-based access

### Areas for Additional Testing

- Google OAuth integration
- Email verification flow
- Password reset functionality
- WebSocket connections
- File upload processing
- Code execution
- Group management UI
- Activity submissions

## Writing New Tests

### Test Structure

```python
import pytest
from app import app as flask_app
from models import initialize_database, create_user

@pytest.fixture
def client(db_path, monkeypatch):
    """Create test client."""
    flask_app.config['DATABASE'] = db_path
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_example(client):
    """Test description."""
    response = client.get('/route')
    assert response.status_code == 200
```

### Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Use fixtures for database setup/teardown
3. **Naming**: Use descriptive test names
4. **Assertions**: Be specific with assertions
5. **Mocking**: Mock external services (email, OAuth)

## Continuous Integration

To run tests in CI/CD:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=. --cov-report=xml
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure project root is in Python path
   - Check `conftest.py` for path setup

2. **Database Locked**
   - Tests use temporary databases, should not occur
   - Check for unclosed database connections

3. **Missing Dependencies**
   - Run `pip install -r requirements.txt`
   - Ensure pytest and pytest-cov are installed

### Debug Mode

Run tests with more verbose output:

```bash
pytest -vv --tb=long
```

## Test Statistics

Run tests and see statistics:

```bash
pytest --collect-only  # List all tests
pytest -v --tb=short   # Verbose with short tracebacks
```

## Contributing Tests

When adding new features:

1. Write tests first (TDD approach)
2. Ensure tests pass before committing
3. Maintain test coverage above 70%
4. Update this document if adding new test categories


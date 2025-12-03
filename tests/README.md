# Test Suite for CodeCraft

This directory contains unit tests for the CodeCraft Flask application.

## Test Structure

- `test_auth.py` - Authentication and user management tests
- `test_code_analysis.py` - Code analysis and detection tests
- `test_models.py` - Database model and operation tests
- `test_utils.py` - Utility function tests
- `test_app.py` - General application route tests
- `conftest.py` - Shared pytest fixtures and configuration

## Running Tests

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_auth.py
pytest tests/test_models.py
pytest tests/test_code_analysis.py
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test

```bash
pytest tests/test_auth.py::TestUserRegistration::test_register_first_user_becomes_admin
```

## Test Coverage

The test suite covers:

1. **Authentication**
   - User registration
   - User login/logout
   - Password management
   - User approval

2. **Database Operations**
   - User CRUD operations
   - Analysis records
   - Groups and activities
   - Submissions

3. **Code Analysis**
   - Code detection endpoints
   - File uploads
   - Analysis history

4. **Protected Routes**
   - Authentication requirements
   - Role-based access control

## Test Fixtures

- `db_path` - Temporary database for each test
- `client` - Flask test client with isolated database
- `logged_in_user` - Pre-authenticated test user

## Notes

- Tests use isolated temporary databases
- No actual email sending in tests (environment variables disabled)
- All tests are independent and can run in any order


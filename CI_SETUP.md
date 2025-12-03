# Continuous Integration Setup

This project includes a GitHub Actions CI workflow for automated testing.

## CI Workflow

The CI workflow (`.github/workflows/ci.yml`) includes:

### Test Job
- **Multi-platform testing**: Runs on Ubuntu, Windows, and macOS
- **Multi-version Python**: Tests on Python 3.9, 3.10, and 3.11
- **Test execution**: Runs all unit tests with coverage reporting
- **Coverage upload**: Uploads coverage reports to Codecov

### Lint Job
- **Code quality**: Runs flake8 and pylint
- **Standards**: Enforces code style and complexity limits

### Security Job
- **Security scanning**: Uses Bandit for security vulnerability detection
- **Dependency checking**: Uses Safety to check for known vulnerabilities in dependencies

## Running Tests Locally

Before pushing, run tests locally:

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v
```

## CI Status Badge

Add this to your README.md to show CI status:

```markdown
![CI](https://github.com/yourusername/yourrepo/workflows/CI/badge.svg)
```

## Workflow Triggers

The CI workflow runs on:
- Push to `main`, `master`, or `develop` branches
- Pull requests to `main`, `master`, or `develop` branches

## Artifacts

The workflow generates:
- Test coverage reports (HTML and XML)
- Test results for each OS/Python version combination

## Requirements

- All tests must pass
- Code coverage should be maintained
- No critical security vulnerabilities
- Code must pass linting checks


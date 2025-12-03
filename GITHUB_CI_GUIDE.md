# GitHub CI Setup Guide

This guide will help you commit the CI workflow to GitHub and verify it's working.

## Step 1: Prepare Files for Commit

### Add CI Workflow File
```bash
git add .github/workflows/ci.yml
```

### Add Test Files
```bash
git add tests/test_*.py
git add tests/conftest.py
git add tests/README.md
```

### Add Documentation
```bash
git add TESTING.md
git add CI_SETUP.md
git add run_tests.py
```

### Add Updated Models
```bash
git add models.py
```

## Step 2: Create .gitignore (if needed)

Make sure these files are NOT committed:
- `__pycache__/` - Python cache files
- `*.pyc` - Compiled Python files
- `database.sqlite3` - Local database
- `.coverage` - Coverage reports
- `htmlcov/` - HTML coverage reports
- `*.db` - Database files

## Step 3: Commit Changes

```bash
git commit -m "Add comprehensive unit tests and GitHub Actions CI workflow

- Add unit tests for authentication, models, code analysis, groups, activities
- Add admin, file management, and notification tests
- Add GitHub Actions CI workflow for automated testing
- Add test documentation and setup guides
- Fix update_user_password function in models.py"
```

## Step 4: Push to GitHub

```bash
git push origin main
```

If you're on a different branch:
```bash
git push origin <your-branch-name>
```

## Step 5: Verify CI is Running

1. Go to your GitHub repository: https://github.com/guillenodlwlrmalvin/aicodechecker
2. Click on the **"Actions"** tab at the top
3. You should see a workflow run starting automatically
4. Click on the workflow run to see details
5. Wait for it to complete (usually 5-10 minutes)

## Step 6: Check Workflow Status

### What to Look For:
- ✅ **Green checkmark** = All tests passed
- ❌ **Red X** = Some tests failed (check logs)
- 🟡 **Yellow circle** = Workflow is running

### View Test Results:
1. Click on the workflow run
2. Click on a job (e.g., "test (ubuntu-latest, 3.11)")
3. Expand "Run tests" to see test output
4. Check "Archive test results" for coverage reports

## Step 7: Add CI Badge to README (Optional)

Add this to your README.md to show CI status:

```markdown
![CI](https://github.com/guillenodlwlrmalvin/aicodechecker/workflows/CI/badge.svg)
```

## Troubleshooting

### If workflow doesn't run:
- Check that the file is in `.github/workflows/ci.yml`
- Verify the YAML syntax is correct
- Check that you're on the correct branch (main/master/develop)

### If tests fail:
- Check the workflow logs for error messages
- Run tests locally: `pytest tests/ -v`
- Fix any failing tests and push again

### If you need to update the workflow:
1. Edit `.github/workflows/ci.yml`
2. Commit and push changes
3. Workflow will run automatically

## Quick Commands Summary

```bash
# Add all test and CI files
git add .github/workflows/ci.yml tests/ TESTING.md CI_SETUP.md run_tests.py models.py

# Commit
git commit -m "Add unit tests and CI workflow"

# Push to GitHub
git push origin main

# Check status
git status
```

## Next Steps

After the CI is set up:
1. Monitor test results on each push
2. Maintain test coverage above 70%
3. Fix any failing tests immediately
4. Review security scan results
5. Keep dependencies updated


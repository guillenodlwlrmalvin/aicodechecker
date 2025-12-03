# PowerShell script to commit and push CI workflow to GitHub

Write-Host "=== Adding CI Workflow and Test Files ===" -ForegroundColor Green

# Add CI workflow
git add .github/workflows/ci.yml
Write-Host "✓ Added CI workflow" -ForegroundColor Green

# Add test files
git add tests/test_*.py tests/conftest.py tests/README.md
Write-Host "✓ Added test files" -ForegroundColor Green

# Add documentation
git add TESTING.md CI_SETUP.md GITHUB_CI_GUIDE.md COMMIT_CI.md run_tests.py
Write-Host "✓ Added documentation" -ForegroundColor Green

# Add models.py
git add models.py
Write-Host "✓ Added models.py" -ForegroundColor Green

# Add .gitignore
git add .gitignore
Write-Host "✓ Added .gitignore" -ForegroundColor Green

Write-Host "`n=== Committing Changes ===" -ForegroundColor Yellow
$msg = "Add comprehensive unit tests and GitHub Actions CI workflow"
git commit -m $msg

Write-Host "✓ Committed changes" -ForegroundColor Green

Write-Host "`n=== Pushing to GitHub ===" -ForegroundColor Yellow
git push origin main

Write-Host "`n=== Done! ===" -ForegroundColor Green
Write-Host "Check your CI workflow at:" -ForegroundColor Cyan
Write-Host "https://github.com/guillenodlwlrmalvin/aicodechecker/actions" -ForegroundColor Magenta

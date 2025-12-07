# PowerShell script to help clean up secrets from git history
# Run this script to remove secret-containing files from git history

Write-Host "=== Git Secrets Cleanup Script ===" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repository
if (-not (Test-Path .git)) {
    Write-Host "Error: Not in a git repository!" -ForegroundColor Red
    exit 1
}

# Show current branch
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "Current branch: $branch" -ForegroundColor Yellow
Write-Host ""

# Check if files with secrets exist in current working directory
$secretFiles = @("setup_google_oauth.ps1", "setup_google_oauth.sh", "setup_google_oauth.bat", "start_app.ps1")
$foundFiles = @()

foreach ($file in $secretFiles) {
    if (Test-Path $file) {
        $foundFiles += $file
        Write-Host "WARNING: $file still exists in working directory!" -ForegroundColor Red
    }
}

if ($foundFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "Please delete these files first:" -ForegroundColor Yellow
    foreach ($file in $foundFiles) {
        Write-Host "  - $file"
    }
    Write-Host ""
    $response = Read-Host "Delete these files now? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        foreach ($file in $foundFiles) {
            Remove-Item $file -Force
            Write-Host "Deleted: $file" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "Choose cleanup method:" -ForegroundColor Cyan
Write-Host "1. Create new clean branch (safest, recommended)"
Write-Host "2. Rewrite history with git filter-branch (destructive)"
Write-Host "3. Show instructions only"
Write-Host ""
$choice = Read-Host "Enter choice (1-3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "=== Creating New Clean Branch ===" -ForegroundColor Cyan
        Write-Host ""
        
        # Get base branch
        $baseBranch = Read-Host "Enter base branch name (main/master)"
        if (-not $baseBranch) { $baseBranch = "main" }
        
        # Checkout base branch
        Write-Host "Checking out $baseBranch..." -ForegroundColor Yellow
        git checkout $baseBranch
        git pull origin $baseBranch
        
        # Create new branch
        $newBranch = Read-Host "Enter new branch name (default: feature-update-clean)"
        if (-not $newBranch) { $newBranch = "feature-update-clean" }
        
        Write-Host "Creating new branch: $newBranch..." -ForegroundColor Yellow
        git checkout -b $newBranch
        
        # Copy changes from old branch (excluding secret files)
        Write-Host "Copying changes from $branch (excluding secret files)..." -ForegroundColor Yellow
        git checkout $branch -- .
        
        # Remove secret files if they exist
        foreach ($file in $secretFiles) {
            if (Test-Path $file) {
                git rm $file 2>$null
                Write-Host "Removed: $file" -ForegroundColor Green
            }
        }
        
        Write-Host ""
        Write-Host "=== Review Changes ===" -ForegroundColor Cyan
        git status
        
        Write-Host ""
        $commit = Read-Host "Commit these changes? (y/n)"
        if ($commit -eq "y" -or $commit -eq "Y") {
            git add .
            git commit -m "Remove all hardcoded secrets and use environment variables"
            Write-Host "Changes committed!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Next step: git push origin $newBranch" -ForegroundColor Yellow
        }
    }
    "2" {
        Write-Host ""
        Write-Host "=== WARNING: This will rewrite git history! ===" -ForegroundColor Red
        Write-Host "This is destructive and will affect all collaborators." -ForegroundColor Red
        Write-Host ""
        $confirm = Read-Host "Are you sure you want to continue? (type 'yes' to confirm)"
        
        if ($confirm -eq "yes") {
            Write-Host ""
            Write-Host "Removing secret files from git history..." -ForegroundColor Yellow
            
            foreach ($file in $secretFiles) {
                Write-Host "Removing $file from history..." -ForegroundColor Yellow
                git filter-branch --force --index-filter "git rm --cached --ignore-unmatch $file" --prune-empty --tag-name-filter cat -- --all
            }
            
            Write-Host ""
            Write-Host "History rewritten!" -ForegroundColor Green
            Write-Host "Next step: git push origin $branch --force" -ForegroundColor Yellow
            Write-Host "WARNING: Force push will overwrite remote history!" -ForegroundColor Red
        } else {
            Write-Host "Cancelled." -ForegroundColor Yellow
        }
    }
    "3" {
        Write-Host ""
        Write-Host "=== Manual Instructions ===" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "See SECURITY_CLEANUP.md for detailed instructions." -ForegroundColor Yellow
    }
    default {
        Write-Host "Invalid choice." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Remember ===" -ForegroundColor Cyan
Write-Host "1. Create a .env file with your actual secrets" -ForegroundColor Yellow
Write-Host "2. Never commit .env to git (it's already in .gitignore)" -ForegroundColor Yellow
Write-Host "3. Use .env.example as a template" -ForegroundColor Yellow
Write-Host ""


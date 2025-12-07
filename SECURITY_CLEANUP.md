# Security Cleanup Guide

GitHub detected secrets in your commit history. Follow these steps to remove them:

## Option 1: Rewrite Git History (Recommended for feature branches)

If you're on a feature branch and haven't merged yet:

```bash
# 1. Make sure all current changes are committed
git add .
git commit -m "Remove all hardcoded secrets and use environment variables"

# 2. Use git filter-branch or BFG Repo-Cleaner to remove secrets from history
# Option A: Using git filter-branch (built-in)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch setup_google_oauth.ps1 setup_google_oauth.sh setup_google_oauth.bat start_app.ps1" \
  --prune-empty --tag-name-filter cat -- --all

# Option B: Using BFG Repo-Cleaner (faster, recommended)
# Download from: https://rtyley.github.io/bfg-repo-cleaner/
# java -jar bfg.jar --delete-files setup_google_oauth.ps1
# java -jar bfg.jar --delete-files setup_google_oauth.sh
# java -jar bfg.jar --delete-files setup_google_oauth.bat
# java -jar bfg.jar --delete-files start_app.ps1

# 3. Force push (WARNING: This rewrites history!)
git push origin feature-update --force
```

## Option 2: Create New Clean Branch (Safest)

If you want to keep history but start fresh:

```bash
# 1. Create a new branch from main/master
git checkout main  # or master
git pull origin main

# 2. Create a new feature branch
git checkout -b feature-update-clean

# 3. Copy all your changes (but not the secret files)
git checkout feature-update -- .
git rm setup_google_oauth.ps1 setup_google_oauth.sh setup_google_oauth.bat start_app.ps1 2>/dev/null || true

# 4. Commit and push
git add .
git commit -m "Add features with secure environment variable configuration"
git push origin feature-update-clean
```

## Option 3: Use git-filter-repo (Modern Tool)

```bash
# Install git-filter-repo first
pip install git-filter-repo

# Remove files from history
git filter-repo --path setup_google_oauth.ps1 --invert-paths
git filter-repo --path setup_google_oauth.sh --invert-paths
git filter-repo --path setup_google_oauth.bat --invert-paths
git filter-repo --path start_app.ps1 --invert-paths

# Force push
git push origin feature-update --force
```

## After Cleanup

1. **Verify secrets are removed:**
   ```bash
   git log --all --full-history -- "*setup_google_oauth*" "*start_app*"
   ```

2. **Set up environment variables:**
   - Create a `.env` file (already in .gitignore)
   - Add your actual secrets to `.env`
   - Never commit `.env` to git

3. **Test the application:**
   ```bash
   python app.py
   ```

## Important Notes

- **Never commit secrets again** - Always use environment variables
- The `.env` file is already in `.gitignore` - it won't be committed
- Use `.env.example` as a template (without real secrets)
- For production, use your hosting platform's environment variable settings


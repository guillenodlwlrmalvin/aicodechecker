# Security Configuration Guide

## Protecting Sensitive Credentials

This application supports multiple ways to configure sensitive credentials without exposing them in Git.

### Configuration Priority (Highest to Lowest):

1. **Environment Variables** (Recommended for production)
2. **local_config.py** (Recommended for development)
3. **Hardcoded fallback values** (Development only - already in Git)

### Setup Instructions

#### Option 1: Use Environment Variables (Best for Production)

Set these environment variables before running the application:

**Windows (PowerShell):**
```powershell
$env:GMAIL_USER = "your-email@gmail.com"
$env:GMAIL_PASS = "your-app-password"
$env:FLASK_SECRET_KEY = "your-secret-key"
```

**Windows (Command Prompt):**
```cmd
set GMAIL_USER=your-email@gmail.com
set GMAIL_PASS=your-app-password
set FLASK_SECRET_KEY=your-secret-key
```

**Linux/Mac:**
```bash
export GMAIL_USER="your-email@gmail.com"
export GMAIL_PASS="your-app-password"
export FLASK_SECRET_KEY="your-secret-key"
```

#### Option 2: Use local_config.py (Best for Development)

1. Copy the example file:
   ```bash
   cp local_config.py.example local_config.py
   ```

2. Edit `local_config.py` and add your credentials:
   ```python
   GMAIL_USER = 'your-email@gmail.com'
   GMAIL_PASS = 'your-app-password'
   FLASK_SECRET_KEY = 'your-secret-key'
   ```

3. The `local_config.py` file is automatically gitignored and will NOT be committed to Git.

### Important Security Notes

⚠️ **The hardcoded credentials in `app.py` are already in Git history. If this is a public repository:**

1. **Rotate your Gmail App Password immediately** - the exposed password is compromised
2. **Change your Flask secret key** - any sessions created with the old key are at risk
3. **Consider using Git history rewriting** (advanced) to remove sensitive data

### What's Protected by .gitignore

The following files are automatically excluded from Git:
- `local_config.py` - Local configuration file
- `*.env` - Environment files
- `*.sqlite3` - Database files
- `uploads/` - User uploaded files
- `__pycache__/` - Python cache files
- And more (see `.gitignore` for full list)

### Verification

To verify your configuration is working:

1. Check the application logs on startup - it will show which Gmail account is configured
2. Try registering a new user - you should receive a verification email
3. If emails don't send, check the logs for configuration warnings


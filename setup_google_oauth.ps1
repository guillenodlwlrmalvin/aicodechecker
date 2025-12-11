# PowerShell script to set Google OAuth and Gmail SMTP environment variables
# Run this before starting the Flask app: .\setup_google_oauth.ps1

Write-Host "Setting environment variables..." -ForegroundColor Green

# Google OAuth
# IMPORTANT: Set these values from your local_config.py or environment variables
# DO NOT commit actual secrets to Git
if (Test-Path "local_config.py") {
    Write-Host "Loading from local_config.py..." -ForegroundColor Cyan
    # local_config.py should contain: GOOGLE_CLIENT_ID = 'your-id-here'
    # This script will read from environment or you can manually set below
}
$env:GOOGLE_CLIENT_ID = $env:GOOGLE_CLIENT_ID ?? "your-google-client-id-here.apps.googleusercontent.com"
$env:GOOGLE_CLIENT_SECRET = $env:GOOGLE_CLIENT_SECRET ?? "your-google-client-secret-here"
$env:GOOGLE_REDIRECT_URI = "http://localhost:5000/auth/google/callback"

# Gmail SMTP
# IMPORTANT: Set these values from your local_config.py or environment variables
$env:GMAIL_USER = $env:GMAIL_USER ?? "your-email@gmail.com"
$env:GMAIL_PASS = $env:GMAIL_PASS ?? "your-app-password-here"

Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Cyan
Write-Host "  GOOGLE_CLIENT_ID=$env:GOOGLE_CLIENT_ID"
Write-Host "  GOOGLE_CLIENT_SECRET=$env:GOOGLE_CLIENT_SECRET"
Write-Host "  GOOGLE_REDIRECT_URI=$env:GOOGLE_REDIRECT_URI"
Write-Host "  GMAIL_USER=$env:GMAIL_USER"
Write-Host "  GMAIL_PASS=*** (configured)" -ForegroundColor Gray
Write-Host ""
Write-Host "To start the Flask app, run: python app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Note: These variables are only set for this PowerShell session." -ForegroundColor Gray
Write-Host "To make them permanent, add them to System Environment Variables." -ForegroundColor Gray
Write-Host ""


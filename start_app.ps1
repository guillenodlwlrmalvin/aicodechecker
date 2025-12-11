# PowerShell script to free port 5000 and start Flask app with Google OAuth
# Usage: .\start_app.ps1

Write-Host "=== Starting CodeCraft Flask App ===" -ForegroundColor Green
Write-Host ""

# Set Google OAuth environment variables
Write-Host "Setting Google OAuth environment variables..." -ForegroundColor Cyan
# Check if local_config.py exists and load from there, otherwise use environment or placeholders
if (Test-Path "local_config.py") {
    Write-Host "  Loading from local_config.py..." -ForegroundColor Gray
}
$env:GOOGLE_CLIENT_ID = $env:GOOGLE_CLIENT_ID ?? "your-google-client-id-here.apps.googleusercontent.com"
$env:GOOGLE_CLIENT_SECRET = $env:GOOGLE_CLIENT_SECRET ?? "your-google-client-secret-here"
$env:GOOGLE_REDIRECT_URI = "http://localhost:5000/auth/google/callback"
Write-Host "✓ Google OAuth variables set" -ForegroundColor Green

# Set Gmail SMTP environment variables
Write-Host "Setting Gmail SMTP environment variables..." -ForegroundColor Cyan
$env:GMAIL_USER = $env:GMAIL_USER ?? "your-email@gmail.com"
$env:GMAIL_PASS = $env:GMAIL_PASS ?? "your-app-password-here"
Write-Host "✓ Gmail SMTP variables set" -ForegroundColor Green
Write-Host ""

# Check if port 5000 is in use
Write-Host "Checking port 5000..." -ForegroundColor Cyan
$portCheck = netstat -ano | findstr :5000
if ($portCheck) {
    Write-Host "⚠ Port 5000 is in use. Attempting to free it..." -ForegroundColor Yellow
    $processes = netstat -ano | findstr :5000 | ForEach-Object {
        if ($_ -match '\s+(\d+)$') {
            $pid = $matches[1]
            Write-Host "  Killing process PID: $pid" -ForegroundColor Yellow
            taskkill /F /PID $pid 2>$null
        }
    }
    Start-Sleep -Seconds 1
    $portCheckAfter = netstat -ano | findstr :5000
    if ($portCheckAfter) {
        Write-Host "✗ Failed to free port 5000. Please close the application using it manually." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "✓ Port 5000 is now free" -ForegroundColor Green
    }
} else {
    Write-Host "✓ Port 5000 is available" -ForegroundColor Green
}
Write-Host ""

# Start the Flask app
Write-Host "Starting Flask app..." -ForegroundColor Cyan
Write-Host "  Server will be available at: http://localhost:5000" -ForegroundColor Gray
Write-Host "  Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""
python app.py


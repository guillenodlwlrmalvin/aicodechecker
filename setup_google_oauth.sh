#!/bin/bash
# Setup script for Google OAuth environment variables on Linux/Mac
# Run this before starting the Flask app: source setup_google_oauth.sh

echo "Setting Google OAuth environment variables..."

# IMPORTANT: Set these values from your local_config.py or environment variables
# DO NOT commit actual secrets to Git
export GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-your-google-client-id-here.apps.googleusercontent.com}"
export GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-your-google-client-secret-here}"
export GOOGLE_REDIRECT_URI="http://localhost:5000/auth/google/callback"

echo ""
echo "Google OAuth environment variables set:"
echo "  GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID"
echo "  GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET"
echo "  GOOGLE_REDIRECT_URI=$GOOGLE_REDIRECT_URI"
echo ""
echo "To start the Flask app, run: python app.py"
echo ""
echo "Note: These variables are only set for this terminal session."
echo "To make them permanent, add them to ~/.bashrc or ~/.zshrc"
echo ""


import os
from flask import Blueprint, redirect, request, session, url_for, jsonify
from google_auth_oauthlib.flow import Flow

google_auth_bp = Blueprint('google_auth', __name__)

def get_google_config():
    """Get config from environment variables."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise ValueError("Google OAuth credentials missing in environment")
    
    return {
        'web': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost:5000/oauth2callback']
        }
    }

@google_auth_bp.route('/google-login')
def google_login():
    config = get_google_config()
    flow = Flow.from_client_config(
        config,
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=config['web']['redirect_uris'][0]
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='select_account'
    )
    session['state'] = state
    return redirect(authorization_url)

@google_auth_bp.route('/oauth2callback')
def oauth_callback():
    # OAuth callback implementation
    return "OAuth callback"

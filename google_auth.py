import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    redirect,
    request,
    session,
    url_for,
    flash,
    jsonify,
)

from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from models import upsert_user_from_google

# Allow HTTP for localhost development (required for OAuth on localhost)
# This should ONLY be used in development, never in production
if os.environ.get('FLASK_ENV') == 'development' or 'localhost' in os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000'):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

google_auth_bp = Blueprint('google_auth', __name__)


def _get_google_client_config():
    """Get Google OAuth client configuration from environment variables."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Require environment variables - no hardcoded fallbacks
    if not client_id or client_id.strip() == '' or client_id.startswith('your_'):
        error_msg = "GOOGLE_CLIENT_ID is missing or not configured. Please set it in environment variables."
        try:
            current_app.logger.error(error_msg)
        except RuntimeError:
            print(f"ERROR: {error_msg}")
        raise ValueError("Google Client ID not configured. Set GOOGLE_CLIENT_ID environment variable.")
    
    if not client_secret or client_secret.strip() == '' or client_secret.startswith('your_'):
        error_msg = "GOOGLE_CLIENT_SECRET is missing or not configured. Please set it in environment variables."
        try:
            current_app.logger.error(error_msg)
        except RuntimeError:
            print(f"ERROR: {error_msg}")
        raise ValueError("Google Client Secret not configured. Set GOOGLE_CLIENT_SECRET environment variable.")
    
    # Get redirect URI from environment or use default
    redirect_uri = os.environ.get(
        'GOOGLE_REDIRECT_URI', 
        'http://localhost:5000/auth/google/callback'
    )
    
    try:
        current_app.logger.info(f"Google OAuth config - Client ID: {client_id[:30]}..., Redirect URI: {redirect_uri}")
        current_app.logger.debug(f"Client Secret configured: {'Yes' if client_secret else 'No'}")
    except RuntimeError:
        pass  # Outside request context
    
    config = {
        'web': {
            'client_id': client_id,
            'project_id': 'codecraft',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
            'client_secret': client_secret,
            'redirect_uris': [
                redirect_uri,
            ],
        }
    }
    
    return config


def _build_flow(state: str | None = None) -> Flow:
    """Build Google OAuth flow with proper configuration."""
    redirect_uri = os.environ.get(
        'GOOGLE_REDIRECT_URI', 
        'http://localhost:5000/auth/google/callback'
    )
    
    # Allow HTTP for localhost development (required for OAuth on localhost)
    # This MUST be set before creating the Flow object
    if redirect_uri.startswith('http://') and ('localhost' in redirect_uri or '127.0.0.1' in redirect_uri):
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        try:
            current_app.logger.debug("Enabled OAUTHLIB_INSECURE_TRANSPORT for localhost development")
        except RuntimeError:
            pass
    
    try:
        current_app.logger.debug(f"Building OAuth flow with redirect_uri: {redirect_uri}, state: {state[:20] if state else None}...")
    except RuntimeError:
        pass
    
    config = _get_google_client_config()
    
    # Ensure redirect_uri matches the one in config
    if redirect_uri not in config['web']['redirect_uris']:
        current_app.logger.warning(f"Redirect URI mismatch: flow={redirect_uri}, config={config['web']['redirect_uris']}")
    
    try:
        flow = Flow.from_client_config(
            config,
            scopes=[
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
            ],
            state=state,
            redirect_uri=redirect_uri,
        )
        current_app.logger.debug("OAuth flow created successfully")
        return flow
    except Exception as e:
        current_app.logger.error(f"Failed to create OAuth flow: {e}", exc_info=True)
        raise


def _handle_google_id_token(google_id_token: str):
    """Verify a Google ID token and return the linked/local user dict and is_new_user flag.
    Returns: (user_dict, is_new_user)
    """
    current_app.logger.info(f"Processing Google ID token (length: {len(google_id_token) if google_id_token else 0})")
    
    client_id = _get_google_client_config()['web']['client_id']
    current_app.logger.debug(f"Using client_id: {client_id[:20]}...")
    
    try:
        current_app.logger.info("Verifying Google ID token...")
        idinfo = id_token.verify_oauth2_token(
            google_id_token,
            google_requests.Request(),
            client_id,
        )
        current_app.logger.info("✓ Google ID token verified successfully")
    except Exception as exc:  # broad but logged
        current_app.logger.error(f'✗ Failed to verify Google ID token: {exc}', exc_info=True)
        raise

    google_id = idinfo.get('sub')
    email = idinfo.get('email')
    name = idinfo.get('name') or email
    avatar = idinfo.get('picture')

    current_app.logger.debug(f"Extracted from token - google_id: {google_id[:20] if google_id else None}..., email: {email}, name: {name}")

    if not google_id or not email:
        current_app.logger.error(f"✗ Missing required claims - google_id: {bool(google_id)}, email: {bool(email)}")
        raise ValueError('Google ID token missing required claims.')

    try:
        current_app.logger.info(f"Upserting user from Google - email: {email}, google_id: {google_id[:20]}...")
        user, is_new_user = upsert_user_from_google(
            current_app.config['DATABASE'],
            google_id=google_id,
            email=email,
            name=name,
            avatar=avatar,
        )
        current_app.logger.info(f"✓ User upserted successfully - username: {user.get('username')}, is_new_user: {is_new_user}")
        return user, is_new_user
    except Exception as exc:
        current_app.logger.error(f'✗ Failed to upsert user from Google: {exc}', exc_info=True)
        raise


@google_auth_bp.route('/login/google')
def login_google():
    """Start the classic redirect-based Google OAuth flow."""
    try:
        # Validate configuration before starting OAuth flow
        config = _get_google_client_config()
        if not config['web']['client_secret']:
            current_app.logger.error("Google OAuth not configured: missing client secret")
            flash('Google OAuth is not properly configured. Please contact the administrator.', 'error')
            return redirect(url_for('login'))
        
        # Make session permanent to ensure it persists across redirects
        session.permanent = True
        
        current_app.logger.info("Starting Google OAuth flow...")
        flow = _build_flow()
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account',
        )
        
        # Store state in session - ensure it's saved
        session['google_oauth_state'] = state
        session.modified = True  # Force session save
        current_app.logger.info(f'✓ OAuth flow initiated, stored state: {state[:20]}...')
        current_app.logger.debug(f'Authorization URL: {authorization_url[:100]}...')
        
        return redirect(authorization_url)
    except ValueError as e:
        # Configuration error
        current_app.logger.error(f"Google OAuth configuration error: {e}")
        flash('Google OAuth is not properly configured. Please contact the administrator.', 'error')
        return redirect(url_for('login'))
    except Exception as e:
        current_app.logger.error(f"Failed to start Google OAuth flow: {e}", exc_info=True)
        flash('Failed to start Google authentication. Please try again.', 'error')
        return redirect(url_for('login'))


@google_auth_bp.route('/auth/google/callback')
def google_callback():
    """Handle OAuth2 redirect flow callback from Google."""
    current_app.logger.info("=== Google OAuth Callback Started ===")
    
    # Make session permanent to ensure it persists
    session.permanent = True
    
    # Get state from session and URL
    stored_state = session.get('google_oauth_state')
    received_state = request.args.get('state')
    
    current_app.logger.debug(f'Stored state: {stored_state[:20] if stored_state else None}...')
    current_app.logger.debug(f'Received state: {received_state[:20] if received_state else None}...')
    
    # Validate state - be more lenient if state is missing (some OAuth flows don't use it)
    if received_state and stored_state and stored_state != received_state:
        current_app.logger.error(f'✗ State mismatch: stored={stored_state[:20]}, received={received_state[:20]}')
        flash('Invalid Google OAuth state. Please try again.', 'error')
        # Clear the invalid state
        session.pop('google_oauth_state', None)
        return redirect(url_for('login'))
    
    # Use received state if available, otherwise stored state
    state_to_use = received_state or stored_state
    current_app.logger.info(f"Using state: {state_to_use[:20] if state_to_use else None}...")
    
    try:
        current_app.logger.info("Building OAuth flow...")
        flow = _build_flow(state=state_to_use)
        current_app.logger.info("✓ OAuth flow built successfully")
    except Exception as exc:
        current_app.logger.error(f"✗ Failed to build OAuth flow: {exc}", exc_info=True)
        flash('Failed to initialize Google OAuth. Please try again.', 'error')
        return redirect(url_for('login'))
    
    try:
        current_app.logger.info(f"Fetching token from authorization response...")
        current_app.logger.debug(f"Full callback URL: {request.url}")
        current_app.logger.debug(f"Request args: {dict(request.args)}")
        
        # Log flow configuration for debugging
        current_app.logger.debug(f"Flow redirect_uri: {flow.redirect_uri}")
        current_app.logger.debug(f"Flow client_id: {flow.client_config.get('client_id', 'N/A')[:30]}...")
        
        # Check for error in callback
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', 'No description')
            current_app.logger.error(f"✗ Google OAuth error in callback: {error} - {error_description}")
            flash(f'Google authentication error: {error_description}', 'error')
            session.pop('google_oauth_state', None)
            return redirect(url_for('login'))
        
        # Fetch the token
        flow.fetch_token(authorization_response=request.url)
        current_app.logger.info("✓ Token fetched successfully")
        
        # Verify we got credentials
        if not flow.credentials:
            current_app.logger.error("✗ No credentials after fetch_token()")
            flash('Failed to get credentials from Google.', 'error')
            session.pop('google_oauth_state', None)
            return redirect(url_for('login'))
            
    except Exception as exc:
        error_type = type(exc).__name__
        error_msg = str(exc)
        current_app.logger.error(f"✗ Token fetch failed: {error_type}: {error_msg}", exc_info=True)
        
        # Provide more specific error messages
        if 'redirect_uri_mismatch' in error_msg.lower():
            flash('Redirect URI mismatch. Please check Google Console configuration.', 'error')
        elif 'invalid_client' in error_msg.lower():
            flash('Invalid client credentials. Please check Client ID and Secret.', 'error')
        elif 'invalid_grant' in error_msg.lower():
            flash('Invalid authorization code. Please try logging in again.', 'error')
        else:
            flash(f'Failed to fetch Google token: {error_msg[:100]}', 'error')
        
        session.pop('google_oauth_state', None)
        return redirect(url_for('login'))

    credentials = flow.credentials
    if not credentials:
        current_app.logger.error("✗ No credentials object returned from flow")
        flash('Google authentication failed: no credentials received.', 'error')
        return redirect(url_for('login'))
    
    if not credentials.id_token:
        current_app.logger.error("✗ No ID token in credentials")
        current_app.logger.debug(f"Credentials type: {type(credentials)}, attributes: {dir(credentials)}")
        flash('Google authentication failed: no token received.', 'error')
        return redirect(url_for('login'))
    
    current_app.logger.info(f"Processing ID token: {credentials.id_token[:50]}...")
    
    try:
        user, is_new_user = _handle_google_id_token(credentials.id_token)
        current_app.logger.info(f"✓ User processed successfully: {user.get('username', 'No username')}")
    except Exception as exc:
        current_app.logger.error(f"✗ User handling failed: {exc}", exc_info=True)
        flash('Failed to process Google user data.', 'error')
        return redirect(url_for('login'))

    # Clear OAuth state
    session.pop('google_oauth_state', None)
    
    # Check if user is verified before allowing login
    is_verified = user.get('is_approved', 0)
    
    if is_new_user:
        # New Google user - send verification code and require verification
        from email_utils import send_verification_email
        verification_code = user.get('verification_token')
        
        if verification_code:
            try:
                send_verification_email(user['username'], verification_code, current_app)
                current_app.logger.info(f"✓ Verification email sent to new Google user: {user['username']}")
                flash('Account created! Please check your email for the 6-digit verification code.', 'info')
            except Exception as e:
                current_app.logger.error(f"Failed to send verification email: {e}")
                flash('Account created! Email sending failed. Your verification code is:', 'warning')
                flash(verification_code, 'info')
        else:
            current_app.logger.warning(f"No verification code found for new Google user: {user['username']}")
            flash('Account created, but verification email could not be sent. Please contact support.', 'error')
        
        return redirect(url_for('verify_code'))
    
    elif not is_verified:
        # Existing user but not verified - resend verification code
        from email_utils import send_verification_email
        from models import set_user_verification_token
        from datetime import datetime, timedelta
        import random
        
        verification_code = user.get('verification_token')
        if not verification_code:
            # Generate new 6-digit code
            verification_code = str(random.randint(100000, 999999))
            expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            set_user_verification_token(current_app.config['DATABASE'], user['id'], verification_code, expires_at)
        
        try:
            send_verification_email(user['username'], verification_code, current_app)
            current_app.logger.info(f"✓ Verification email resent to Google user: {user['username']}")
            flash('Your account is not verified yet. A verification code has been sent to your email.', 'warning')
        except Exception as e:
            current_app.logger.error(f"Failed to send verification email: {e}")
            flash('Your account is not verified. Email sending failed. Your verification code is:', 'warning')
            flash(verification_code, 'info')
        
        return redirect(url_for('verify_code'))
    
    else:
        # Existing verified user - allow login
        session['user_id'] = user['username']
        session.modified = True
        flash('Logged in with Google successfully.', 'success')
        return redirect(url_for('dashboard'))


@google_auth_bp.route('/api/auth/google', methods=['POST'])
def api_google_auth():
    """
    Accept Google Identity Services credential (ID token) from frontend JS.
    Expected body: { "credential": "<ID_TOKEN>" }
    """
    data = request.get_json(silent=True) or {}
    credential = data.get('credential')
    if not credential:
        return jsonify({'success': False, 'error': 'Missing credential'}), 400

    try:
        user, is_new_user = _handle_google_id_token(credential)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid Google token'}), 401

    # Check if user is verified
    is_verified = user.get('is_approved', 0)
    
    if not is_verified:
        # User not verified - send verification code
        from email_utils import send_verification_email
        from models import set_user_verification_token
        from datetime import datetime, timedelta
        import random
        
        verification_code = user.get('verification_token')
        if not verification_code:
            # Generate new 6-digit code
            verification_code = str(random.randint(100000, 999999))
            expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            set_user_verification_token(current_app.config['DATABASE'], user['id'], verification_code, expires_at)
        
        try:
            send_verification_email(user['username'], verification_code, current_app)
            current_app.logger.info(f"✓ Verification email sent to Google user: {user['username']}")
        except Exception as e:
            current_app.logger.error(f"Failed to send verification email: {e}")
        
        return jsonify({
            'success': False,
            'error': 'Account not verified',
            'message': 'Please check your email for the 6-digit verification code.',
            'requires_verification': True
        }), 403
    
    # User is verified - allow login
    session['user_id'] = user['username']
    return jsonify(
        {
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['username'],
                'name': user.get('name') or user['username'],
                'avatar': user.get('avatar'),
            },
            'is_new_user': is_new_user,
        }
    )



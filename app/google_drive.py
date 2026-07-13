import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CRITICAL FIX: explicit blueprint declaration with name matching '__init__.py'
drive_bp = Blueprint('drive', __name__)

# Enforce HTTPS for OAuth Callback in production (Render)
if os.environ.get('FLASK_ENV') == 'production' or 'render.com' in os.environ.get('RENDER_EXTERNAL_URL', ''):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'
else:
    # Allows HTTP for local development testing
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_google_config():
    """Generates the client configuration dynamically from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    # Getting dynamic redirect URI based on Render host or fallback to local
    external_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
    redirect_uri = f"{external_url.rstrip('/')}/oauth2callback"

    if not client_id or not client_secret:
        raise ValueError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in Environment Variables!")

    return {
        "web": {
            "client_id": client_id,
            "project_id": "freight-crm-backup",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri]
        }
    }, redirect_uri

# ==========================================
# OAUTH FLOW ROUTES
# ==========================================

@drive_bp.route('/login/google')
def login_google():
    """Initiates the Google OAuth 2.0 Authentication Flow."""
    client_config, redirect_uri = get_google_config()
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    # access_type='offline' ensures we get a Refresh Token
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='select_account consent'
    )
    
    # Save state to session to prevent CSRF attacks
    session['oauth_state'] = state
    return redirect(authorization_url)

@drive_bp.route('/oauth2callback')
def oauth2callback():
    """Handles the redirection back from Google and exchanges code for tokens."""
    state = session.get('oauth_state')
    client_config, redirect_uri = get_google_config()

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri
    )
    
    # Fetch tokens
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    # Save credentials into session or database
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    logger.info("OAuth Authorization Successful! Tokens stored in session.")
    return jsonify({"status": "success", "message": "Google Drive authenticated successfully! You can close this tab now."})

# ==========================================
# DRIVE OPERATIONS (BACKUP FUNCTION)
# ==========================================

def load_credentials():
    """Loads and refreshes credentials if needed."""
    creds_data = session.get('credentials')
    if not creds_data:
        return None

    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    # Refresh the token automatically if it expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            session['credentials']['token'] = creds.token
            logger.info("Google OAuth token auto-refreshed.")
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return None

    return creds

def upload_backup_to_drive(file_path, folder_name="Freight_CRM_Prod_Backups"):
    """Uploads database backup file to user's Google Drive inside a dedicated folder."""
    creds = load_credentials()
    if not creds:
        logger.error("User not authenticated. Please hit /login/google first.")
        return False, "Authentication Required"

    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Check if folder exists
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        items = results.get('files', [])
        
        if items:
            folder_id = items[0]['id']
        else:
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')

        # Upload the file
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        return True, uploaded_file.get('id')

    except Exception as e:
        logger.error(f"An error occurred during file upload: {e}")
        return False, str(e)
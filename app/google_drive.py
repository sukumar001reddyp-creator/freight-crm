# app/google_drive.py
import os
import pickle
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import url_for, session, redirect, flash, request, current_app
from app.models import BackupLog
from werkzeug.utils import secure_filename

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_google_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": current_app.config.get('GOOGLE_CLIENT_ID'),
                "client_secret": current_app.config.get('GOOGLE_CLIENT_SECRET'),
                "redirect_uris": [current_app.config.get('GOOGLE_REDIRECT_URI')],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=current_app.config.get('GOOGLE_REDIRECT_URI')
    )


def login_google():
    """Start Google OAuth flow"""
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['google_oauth_state'] = state
    return redirect(authorization_url)


def oauth2callback():
    """Google OAuth callback"""
    state = session.get('google_oauth_state')
    flow = get_google_flow()
    flow.state = state

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        token_path = os.path.join(os.getcwd(), 'google_token.pickle')
        with open(token_path, 'wb') as token:
            pickle.dump(credentials, token)

        flash("✅ Google account successfully linked!", "success")
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"❌ Google login failed: {str(e)}", "danger")
        return redirect(url_for('dashboard'))


def backup_to_google_drive(zip_path, filename):
    """Upload backup to Google Drive"""
    try:
        token_path = os.path.join(os.getcwd(), 'google_token.pickle')
        
        if not os.path.exists(token_path):
            return False, "Google account not linked. Please login first."

        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {'name': filename, 'mimeType': 'application/zip'}
        media = MediaFileUpload(zip_path, mimetype='application/zip', resumable=True)

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        BackupLog.create(
            filename=filename,
            status='success',
            file_id=file.get('id')
        )

        return True, file.get('id')

    except Exception as e:
        BackupLog.create(filename=filename, status='failed', error=str(e))
        return False, str(e)
import os
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Handles silent background token loading without Flask context dependence."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in Environment Variables!")
        return None

    # Production token credentials payload template injection
    # Render cloud containers dynamically map credentials tokens here
    token_json = os.environ.get("GOOGLE_DRIVE_TOKEN")
    
    creds = None
    if token_json:
        try:
            import json
            creds_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        except Exception as e:
            logger.error(f"Error decoding GOOGLE_DRIVE_TOKEN: {e}")

    # Token expiry refresh state processing matrix
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            logger.error(f"Failed to auto-refresh Google token: {e}")
            creds = None

    if not creds:
        logger.error("Google Drive Token Missing or Expired! Please configure GOOGLE_DRIVE_TOKEN.")
        return None

    return build('drive', 'v3', credentials=creds)

def upload_backup_to_drive(file_path, folder_name="Freight_CRM_Prod_Backups"):
    """Standalone system tool execution to copy local backup files to Google Drive."""
    service = get_drive_service()
    if not service:
        return False, "Google Drive API Service Account Auth Matrix Not Ready"

    try:
        # Check if the folder already exists
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
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")

        # Execute upload operation targeting the cloud workspace path
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

        logger.info(f"Backup file synchronized to Drive. File ID: {uploaded_file.get('id')}")
        return True, uploaded_file.get('id')

    except Exception as e:
        logger.error(f"An error occurred during standalone drive tracking: {e}")
        return False, str(e)
import io
import json
import os

from flask import current_app

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/drive.file"
]


def get_drive_service():
    """
    Creates authenticated Google Drive service
    using the JSON stored in the environment variable:
    GOOGLE_SERVICE_ACCOUNT_JSON
    """

    json_string = current_app.config.get(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    if not json_string:
        raise Exception(
            "GOOGLE_SERVICE_ACCOUNT_JSON not configured."
        )

    credentials_info = json.loads(
        json_string
    )

    credentials = (
        service_account.Credentials
        .from_service_account_info(
            credentials_info,
            scopes=SCOPES,
        )
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def get_backup_folder_id(service):
    """
    Finds the FreightCRM_Backups folder.
    Creates it if it doesn't exist.
    """

    folder_name = current_app.config.get(
        "GOOGLE_DRIVE_BACKUP_FOLDER",
        "FreightCRM_Backups"
    )

    query = (
        "mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name}' "
        "and trashed=false"
    )

    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
    ).execute()

    folders = result.get(
        "files",
        []
    )

    if folders:
        return folders[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }

    folder = service.files().create(
        body=metadata,
        fields="id",
    ).execute()

    return folder["id"]


def upload_to_google_drive(file_path):
    """
    Uploads backup file to Google Drive.
    """

    if not os.path.exists(file_path):
        raise Exception(
            f"Backup file not found: {file_path}"
        )

    service = get_drive_service()

    folder_id = get_backup_folder_id(
        service
    )

    filename = os.path.basename(
        file_path
    )

    media = MediaFileUpload(
        file_path,
        resumable=True,
    )

    metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name",
    ).execute()

    return uploaded
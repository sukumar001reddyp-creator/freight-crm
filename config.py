import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "freight-crm-dev-secret-key"
    )

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # === BACKUP SCHEDULER SETTINGS ===
    BACKUP_ENABLED = True
    BACKUP_TIME = "00:00"              # 00:00 IST (Midnight)
    BACKUP_RETENTION_DAYS = 7          # Keep last 7 backups

    # LOCAL DOWNLOADS FOLDER
    BACKUP_FOLDER = os.path.join(
        os.path.expanduser("~"),
        "Downloads",
        "FreightCRM_Backups"
    )

    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    GOOGLE_DRIVE_BACKUP_FOLDER = os.getenv(
        "GOOGLE_DRIVE_BACKUP_FOLDER",
        "FreightCRM_Backups"
    )
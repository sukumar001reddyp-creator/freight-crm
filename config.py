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

    SQLALCHEMY_DATABASE_URI = (
        database_url or "sqlite:///freight_crm.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BACKUP_ENABLED = True
    BACKUP_TIME = "02:00"
    MAX_BACKUPS = 30

    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )

    GOOGLE_DRIVE_BACKUP_FOLDER = os.getenv(
        "GOOGLE_DRIVE_BACKUP_FOLDER",
        "FreightCRM_Backups"
    )
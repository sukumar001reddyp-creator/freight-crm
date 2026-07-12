import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "freight-crm-dev-secret-key"
    )

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///freight_crm.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BACKUP_ENABLED = True

    BACKUP_TIME = "02:00"

    MAX_BACKUPS = 30
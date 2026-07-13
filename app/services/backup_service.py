import os
import shutil
import subprocess
from datetime import datetime
from urllib.parse import urlparse


from flask import current_app
from app.services.google_drive import upload_to_google_drive

def backup_directory():
    folder = os.path.join(current_app.root_path, "backups")
    os.makedirs(folder, exist_ok=True)
    return folder


def backup_filename(extension):
    return datetime.now().strftime(
        f"freightcrm_%Y%m%d_%H%M%S.{extension}"
    )


def create_backup():
    database_url = current_app.config.get("SQLALCHEMY_DATABASE_URI")

    if not database_url:
        raise Exception("Database URL not configured.")

    # ----------------------------------
    # SQLITE BACKUP
    # ----------------------------------
    if database_url.startswith("sqlite"):
        db_path = database_url.replace("sqlite:///", "")

        if not os.path.isabs(db_path):
            db_path = os.path.join(
                current_app.instance_path or os.path.join(os.getcwd(), "instance"),
                db_path.lstrip("/")
            )

        if not os.path.exists(db_path):
            db_path = os.path.join(os.getcwd(), "instance", "freight_crm.db")

        if not os.path.exists(db_path):
            raise Exception(f"SQLite database not found: {db_path}")

        backup_file = os.path.join(
            backup_directory(),
            backup_filename("db")
        )

        shutil.copy2(db_path, backup_file)

        cleanup_old_backups()

# Google Drive upload
        upload_to_google_drive(
            backup_file
)

        return backup_file

    # ----------------------------------
    # POSTGRES BACKUP
    # ----------------------------------
    if database_url.startswith(("postgres", "postgresql")):
        backup_file = os.path.join(
            backup_directory(),
            backup_filename("sql")
        )

        url = urlparse(database_url)
        env = os.environ.copy()
        if url.password:
            env["PGPASSWORD"] = url.password

        command = [
            "pg_dump",
            "-h", url.hostname or "localhost",
            "-p", str(url.port or 5432),
            "-U", url.username or "postgres",
            "-d", url.path.lstrip("/"),
            "-F", "p",
            "-f", backup_file,
        ]

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise Exception(f"pg_dump failed: {result.stderr}")

        cleanup_old_backups()

        try:
            upload_to_google_drive(backup_file)
        except Exception as e:
            print("Google Drive Upload Failed:", e)

        return backup_file  

    raise Exception("Unsupported database type.")


def backup_history():
    folder = backup_directory()
    backups = []

    for file in os.listdir(folder):
        if file.endswith((".db", ".sql")):
            path = os.path.join(folder, file)
            backups.append({
                "name": file,
                "size": round(os.path.getsize(path) / 1024, 2),
                "created": datetime.fromtimestamp(os.path.getctime(path))
            })

    backups.sort(key=lambda x: x["created"], reverse=True)
    return backups


def database_info():
    database_url = current_app.config.get("SQLALCHEMY_DATABASE_URI")

    info = {
        "type": "Unknown",
        "size": "0 KB",
        "healthy": True,
    }

    if not database_url:
        return info

    if database_url.startswith("sqlite"):
        info["type"] = "SQLite"
        db_path = database_url.replace("sqlite:///", "")

        if not os.path.isabs(db_path):
            db_path = os.path.join(
                current_app.instance_path or os.path.join(os.getcwd(), "instance"),
                db_path.lstrip("/")
            )

        if os.path.exists(db_path):
            info["size"] = f"{round(os.path.getsize(db_path) / 1024, 2)} KB"

    elif database_url.startswith(("postgres", "postgresql")):
        info["type"] = "PostgreSQL"

    return info


def restore_backup(filename):

    backup_file = os.path.join(
        backup_directory(),
        filename
    )

    if not os.path.exists(backup_file):
        raise Exception(
            "Backup file not found."
        )

    database_url = current_app.config.get(
        "SQLALCHEMY_DATABASE_URI"
    )

    if database_url.startswith("sqlite"):

        db_path = database_url.replace(
            "sqlite:///",
            ""
        )

        if not os.path.isabs(db_path):
            db_path = os.path.join(
                current_app.instance_path,
                db_path
            )

        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(
                os.path.dirname(db_path),
                exist_ok=True
            )

        # Existing DB unte emergency backup create cheyyi
        if os.path.exists(db_path):

            emergency_backup = (
                db_path +
                ".before_restore"
            )

            print("Backup File :", backup_file)
            print("Database File :", db_path)
            print("Backup Exists :", os.path.exists(backup_file))

            shutil.copy2(
                db_path,
                emergency_backup
            )

        # Backup file ni database ga restore cheyyi
        shutil.copy2(
            backup_file,
            db_path
        )

        return True

    raise Exception(
        "Restore currently supports SQLite only."
    )


def cleanup_old_backups(keep=30):
    backups = backup_history()

    if len(backups) <= keep:
        return

    for backup in backups[keep:]:

        path = os.path.join(
            backup_directory(),
            backup["name"]
        )

        if os.path.exists(path):
            os.remove(path)
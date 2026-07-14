# app/services/backup_service.py
import os
from datetime import datetime
from flask import current_app
from app.google_drive import upload_backup_to_drive
from app.models import BackupLog


def create_backup():
    """Create database backup and upload to Google Drive"""
    try:
        with current_app.app_context():

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"freight_crm_backup_{timestamp}.zip"
            backup_dir = "backups"
            backup_path = os.path.join(backup_dir, filename)

            os.makedirs(backup_dir, exist_ok=True)

            db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI')
            if not db_url:
                raise Exception("Database URL not configured")

            os.system(f"pg_dump {db_url} > {backup_path} 2>/dev/null")

            if not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0:
                raise Exception("Backup file creation failed")

            success, result = backup_to_google_drive(backup_path, filename)

            if success:
                BackupLog.create(filename=filename, status="success", file_id=result)
                print(f"✅ Backup successful: {filename}")
                return True
            else:
                BackupLog.create(filename=filename, status="failed", error=result)
                print(f"❌ Backup failed: {result}")
                return False

    except Exception as e:
        print(f"Backup error: {str(e)}")
        return False


def backup_history():
    """Return recent backup logs"""
    from app.models import BackupLog
    return BackupLog.query.order_by(BackupLog.created_at.desc()).limit(10).all()


def database_info():
    """Return basic database info"""
    try:
        with current_app.app_context():
            from sqlalchemy import text
            result = db.session.execute(text("SELECT version()")).scalar()
            return {"database_version": result}
    except:
        return {"database_version": "Unknown"}


def restore_backup(backup_filename):
    """Restore from backup (placeholder)"""
    print(f"Restore from {backup_filename} - Not implemented yet")
    return False, "Restore functionality coming soon"
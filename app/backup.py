import os
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory,
    current_app,
    send_file,
    request
)
from flask_login import (
    login_required,
    current_user,
)
from sqlalchemy import DateTime, Date, text

# === SCHEDULER IMPORTS ===
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
import atexit

# === GOOGLE DRIVE IMPORTS ===
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

backup_bp = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)

logger = logging.getLogger(__name__)

# Global scheduler
backup_scheduler = None

# Default local backup folder
DEFAULT_BACKUP_FOLDER = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "FreightCRM_Backups"
)


def admin_only():
    return getattr(current_user, "role", "") == "admin"


def get_backup_folder():
    """Get backup folder from config or default"""
    return current_app.config.get(
        'BACKUP_FOLDER',
        DEFAULT_BACKUP_FOLDER
    )


# =========================================================
# GOOGLE DRIVE UPLOAD FUNCTION
# =========================================================

def upload_to_drive(file_path, filename):
    """Upload backup to Google Drive"""
    try:
        # Get credentials from environment
        creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not creds_json:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON not found")
            return None

        # Parse JSON
        creds_info = json.loads(creds_json)

        # Build credentials
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/drive']
        )

        # Build Drive service
        service = build('drive', 'v3', credentials=credentials)

        # Get folder ID from config
        folder_id = current_app.config.get('GOOGLE_DRIVE_BACKUP_FOLDER')

        # Upload file
        file_metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }

        media = MediaFileUpload(
            file_path,
            mimetype='application/json',
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_id = file.get('id')
        web_link = file.get('webViewLink')

        logger.info(f"✅ Uploaded to Drive: {web_link}")
        return file_id

    except Exception as e:
        logger.error(f"❌ Drive upload failed: {e}")
        return None


# =========================================================
# ROUTES
# =========================================================

@backup_bp.route("/")
@login_required
def index():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    backup_dir = get_backup_folder()
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.json'):
                fpath = os.path.join(backup_dir, f)
                backups.append({
                    'filename': f,
                    'created': datetime.fromtimestamp(
                        os.path.getctime(fpath)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    'size': f"{os.path.getsize(fpath) / 1024:.1f} KB",
                    'type': 'Auto' if f.startswith('auto_') else 'Manual'
                })

    return render_template(
        "backup/index.html",
        backups=backups,
        backup_folder=backup_dir
    )


@backup_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    try:
        from app.models import db

        backup_dir = get_backup_folder()
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.json"
        dest_path = os.path.join(backup_dir, backup_filename)

        table_order = [t.name for t in db.metadata.sorted_tables]

        backup_data = {}
        for table_name in table_order:
            if table_name in db.metadata.tables:
                try:
                    table = db.metadata.tables[table_name]
                    result = db.session.execute(table.select()).fetchall()
                    backup_data[table_name] = [
                        dict(row._mapping) for row in result
                    ]
                    logger.info(f"Backed up {table_name}: {len(result)} rows")
                except Exception as table_err:
                    logger.error(f"Error reading {table_name}: {table_err}")
                    backup_data[table_name] = f"Error: {str(table_err)}"

        def universal_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            try:
                return str(obj)
            except Exception:
                raise TypeError(f"Type {type(obj)} not serializable")

        with open(dest_path, "w") as f:
            json.dump(backup_data, f, indent=4, default=universal_serializer)

        logger.info(f"Backup saved: {dest_path}")

        # === UPLOAD TO GOOGLE DRIVE ===
        file_id = upload_to_drive(dest_path, backup_filename)
        if file_id:
            flash(f"✅ Uploaded to Google Drive!", "success")

        return send_file(
            dest_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/json'
        )

    except Exception as e:
        logger.exception("Backup creation failed")
        flash(f"Backup creation failed: {str(e)}", "danger")
        return redirect(url_for("backup.index"))


@backup_bp.route("/download/<filename>")
@login_required
def download(filename):
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    folder = get_backup_folder()
    file_path = os.path.join(folder, filename)

    if not os.path.exists(file_path):
        flash("Backup file not found.", "danger")
        return redirect(url_for("backup.index"))

    return send_from_directory(folder, filename, as_attachment=True)


@backup_bp.route("/delete/<filename>")
@login_required
def delete(filename):
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    file_path = os.path.join(get_backup_folder(), filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        flash("Backup deleted successfully.", "success")
    else:
        flash("Backup file not found.", "danger")

    return redirect(url_for("backup.index"))


@backup_bp.route("/restore", methods=["POST"])
@login_required
def restore():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    try:
        from app.models import db

        if 'backup_file' not in request.files:
            flash("No file part found", "danger")
            return redirect(url_for("backup.index"))

        file = request.files['backup_file']
        logger.info(f"Uploaded file: {file.filename}")

        if file.filename == '':
            flash("No selected file", "danger")
            return redirect(url_for("backup.index"))

        if not file.filename.endswith('.json'):
            flash("Invalid file format.", "danger")
            return redirect(url_for("backup.index"))

        file_data = json.load(file)
        logger.info(f"Backup contains tables: {list(file_data.keys())}")

        sorted_tables = [t.name for t in db.metadata.sorted_tables]
        matching_tables = [t for t in sorted_tables if t in file_data]

        if not matching_tables:
            flash("No matching tables found in backup!", "danger")
            return redirect(url_for("backup.index"))

        # Clear tables
        for table_name in reversed(sorted_tables):
            if table_name in db.metadata.tables and table_name in file_data:
                table = db.metadata.tables[table_name]
                try:
                    db.session.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
                except Exception:
                    db.session.execute(table.delete())

        db.session.commit()

        # Restore data
        total_rows = 0
        skipped_columns = {}

        for table_name in sorted_tables:
            if table_name not in file_data:
                continue

            rows = file_data[table_name]
            if not isinstance(rows, list):
                continue

            table = db.metadata.tables[table_name]
            actual_columns = set(table.columns.keys())

            table_skipped = set()
            table_inserted = 0

            for row in rows:
                cleaned_row = {}
                for col_name, value in row.items():
                    if col_name not in actual_columns:
                        table_skipped.add(col_name)
                        continue

                    col_type = table.columns[col_name].type

                    if value is None:
                        cleaned_row[col_name] = None
                    elif isinstance(col_type, DateTime) and isinstance(value, str):
                        try:
                            cleaned_row[col_name] = datetime.fromisoformat(value)
                        except ValueError:
                            cleaned_row[col_name] = value
                    elif isinstance(col_type, Date) and isinstance(value, str):
                        try:
                            cleaned_row[col_name] = datetime.fromisoformat(value).date()
                        except ValueError:
                            cleaned_row[col_name] = value
                    else:
                        cleaned_row[col_name] = value

                if cleaned_row:
                    try:
                        db.session.execute(table.insert().values(**cleaned_row))
                        table_inserted += 1
                        total_rows += 1
                    except Exception as insert_err:
                        logger.error(f"Insert failed: {insert_err}")
                        continue

            # Commit per table
            try:
                db.session.commit()
            except Exception as commit_err:
                db.session.rollback()
                logger.error(f"Commit failed for {table_name}: {commit_err}")
                continue

            if table_skipped:
                skipped_columns[table_name] = list(table_skipped)

        msg = f"Database restored! {total_rows} rows."
        if skipped_columns:
            skip_details = ", ".join([
                f"{t}: {len(cols)} cols" 
                for t, cols in skipped_columns.items()
            ])
            msg += f" Skipped: {skip_details}."

        flash(msg, "success")
        logger.info(f"Restore complete: {total_rows} rows")

    except Exception as e:
        db.session.rollback()
        logger.exception("Restore failed")
        flash(f"Recovery failed: {str(e)}", "danger")

    return redirect(url_for("backup.index"))


# =========================================================
# SCHEDULER (00:00 IST Daily) + GOOGLE DRIVE UPLOAD
# =========================================================

def init_backup_scheduler(app):
    """Initialize daily backup scheduler at 00:00 IST"""
    global backup_scheduler

    if not app.config.get('BACKUP_ENABLED', False):
        logger.info("Backup scheduler disabled")
        return

    ist = timezone('Asia/Kolkata')
    backup_time = app.config.get('BACKUP_TIME', '00:00')
    hour, minute = map(int, backup_time.split(':'))

    backup_scheduler = BackgroundScheduler()

    backup_scheduler.add_job(
        func=lambda: run_scheduled_backup(app),
        trigger=CronTrigger(hour=hour, minute=minute, timezone=ist),
        id='daily_backup',
        name=f'Daily Backup ({backup_time} IST)',
        replace_existing=True
    )

    backup_scheduler.start()
    app.logger.info(f"✅ Backup scheduled daily at {backup_time} IST")
    app.logger.info(f"📁 Local folder: {app.config.get('BACKUP_FOLDER', DEFAULT_BACKUP_FOLDER)}")
    app.logger.info(f"☁️ Google Drive folder: {app.config.get('GOOGLE_DRIVE_BACKUP_FOLDER', 'Not set')}")

    atexit.register(
        lambda: backup_scheduler.shutdown() if backup_scheduler else None
    )


def run_scheduled_backup(app):
    """Run backup, upload to Google Drive, cleanup"""
    with app.app_context():
        try:
            from app.models import db

            backup_dir = app.config.get('BACKUP_FOLDER', DEFAULT_BACKUP_FOLDER)
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                app.logger.info(f"Created folder: {backup_dir}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"auto_backup_{timestamp}.json"
            dest_path = os.path.join(backup_dir, backup_filename)

            table_order = [t.name for t in db.metadata.sorted_tables]
            backup_data = {}

            for table_name in table_order:
                if table_name in db.metadata.tables:
                    table = db.metadata.tables[table_name]
                    result = db.session.execute(table.select()).fetchall()
                    backup_data[table_name] = [
                        dict(row._mapping) for row in result
                    ]

            def universal_serializer(obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if isinstance(obj, Decimal):
                    return float(obj)
                try:
                    return str(obj)
                except Exception:
                    raise TypeError(f"Type {type(obj)} not serializable")

            with open(dest_path, "w") as f:
                json.dump(backup_data, f, indent=4, default=universal_serializer)

            app.logger.info(f"✅ Backup created: {backup_filename}")

            # === UPLOAD TO GOOGLE DRIVE ===
            file_id = upload_to_drive(dest_path, backup_filename)

            if file_id:
                # Save to BackupLog
                from app.models import BackupLog
                log = BackupLog(
                    filename=backup_filename,
                    status='uploaded',
                    file_id=file_id
                )
                db.session.add(log)
                db.session.commit()
                app.logger.info(f"✅ Backup uploaded to Drive: {file_id}")
            else:
                app.logger.warning("⚠️ Drive upload failed, backup saved locally only")

            # Cleanup old local backups
            cleanup_old_backups(app)

        except Exception as e:
            app.logger.error(f"❌ Auto backup failed: {e}")


def cleanup_old_backups(app):
    """Delete old backups from local folder"""
    try:
        backup_dir = app.config.get('BACKUP_FOLDER', DEFAULT_BACKUP_FOLDER)
        retention_days = app.config.get('BACKUP_RETENTION_DAYS', 7)
        cutoff = datetime.now().timestamp() - (retention_days * 86400)

        deleted = 0
        for filename in os.listdir(backup_dir):
            if filename.startswith('auto_backup_') and filename.endswith('.json'):
                filepath = os.path.join(backup_dir, filename)
                if os.path.getctime(filepath) < cutoff:
                    os.remove(filepath)
                    deleted += 1

        if deleted:
            app.logger.info(f"🗑️ Deleted {deleted} old local backups")

    except Exception as e:
        app.logger.error(f"Cleanup failed: {e}")


# =========================================================
# MANUAL TRIGGER / SCHEDULE INFO
# =========================================================

@backup_bp.route("/schedule")
@login_required
def schedule_info():
    """Show backup schedule"""
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    jobs = []
    if backup_scheduler:
        for job in backup_scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.strftime(
                    "%Y-%m-%d %H:%M:%S %Z"
                ) if job.next_run_time else 'Not scheduled'
            })

    return render_template(
        "backup/schedule.html",
        jobs=jobs,
        backup_folder=get_backup_folder()
    )


@backup_bp.route("/run-now", methods=["POST"])
@login_required
def run_now():
    """Manually trigger backup"""
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    try:
        run_scheduled_backup(current_app._get_current_object())
        flash("✅ Manual backup completed! Check Google Drive.", "success")
    except Exception as e:
        flash(f"❌ Manual backup failed: {e}", "danger")

    return redirect(url_for('backup.index'))
import os
import shutil
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory,
    current_app,
    session
)
from flask_login import (
    login_required,
    current_user,
)
from app.services.backup_service import (
    create_backup,
    backup_history,
    database_info,
    restore_backup,
)

backup_bp = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)


def admin_only():
    return getattr(current_user, "role", "") == "admin"


@backup_bp.route("/")
@login_required
def index():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    return render_template(
        "backup/index.html",
        backups=backup_history(),
        db_info=database_info(),
    )


@backup_bp.route("/create")
@login_required
def create():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    # FIX: Direct dynamic string check - routing matrix build error raadhu ika
    if 'credentials' not in session:
        flash("Google Drive authorization missing! Redirecting to Google Login...", "warning")
        return redirect("/login/google")

    try:
        # 1. Create local backup file
        create_backup()
        
        # 2. Pick the latest backup file path
        history = backup_history()
        if history:
            latest_backup_filename = history[0]['filename']
            local_backup_path = os.path.join(
                current_app.root_path,
                "backups",
                latest_backup_filename
            )
            
            # FIX: Lazy import inside function block to prevent cyclic error
            from app.google_drive import upload_backup_to_drive 
            
            # 3. Stream backup directly to Google Drive
            success, drive_response = upload_backup_to_drive(
                local_backup_path, 
                folder_name="Freight_CRM_Prod_Backups"
            )
            
            if success:
                flash(f"Database backup created and synced to Google Drive successfully! File ID: {drive_response}", "success")
            else:
                flash(f"Backup created locally, but Google Drive Sync Failed: {drive_response}", "warning")
        else:
            flash("Database backup created locally, but failed to locate file for Google Drive sync.", "warning")

    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("backup.index"))


@backup_bp.route("/auto")
def auto_backup():
    try:
        create_backup()
        return "Backup Created", 200
    except Exception as e:
        return str(e), 500


@backup_bp.route("/download/<filename>")
@login_required
def download(filename):
    if not admin_only():
        return redirect(url_for("dashboard"))

    folder = os.path.join(current_app.root_path, "backups")
    return send_from_directory(folder, filename, as_attachment=True)


@backup_bp.route("/restore/<filename>")
@login_required
def restore(filename):
    if not admin_only():
        return redirect(url_for("dashboard"))

    try:
        restore_backup(filename)
        flash("Database restored successfully. Please restart the application.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("backup.index"))


@backup_bp.route("/delete/<filename>")
@login_required
def delete(filename):
    if not admin_only():
        return redirect(url_for("dashboard"))

    file_path = os.path.join(current_app.root_path, "backups", filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        flash("Backup deleted successfully.", "success")
    else:
        flash("Backup file not found.", "danger")

    return redirect(url_for("backup.index"))
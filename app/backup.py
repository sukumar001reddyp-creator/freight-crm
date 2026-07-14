import os
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory,
    current_app
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


import os
import shutil
from datetime import datetime
from flask import current_app, flash, redirect, url_for, send_file
from app.backup import backup_bp

@backup_bp.route("/create", methods=["GET", "POST"])
def create():
    try:
        # 1. Ensure the backup directory exists
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        dest_path = os.path.join(backup_dir, backup_filename)

        # 2. Smart DB Path Discovery (Checks instance path first, then root path)
        instance_db = os.path.join(current_app.instance_path, 'freight_crm.db')
        root_db = os.path.join(current_app.root_path, 'freight_crm.db')
        parent_root_db = os.path.abspath(os.path.join(current_app.root_path, '..', 'freight_crm.db'))
        
        selected_db_path = None
        
        if os.path.exists(instance_db):
            selected_db_path = instance_db
        elif os.path.exists(root_db):
            selected_db_path = root_db
        elif os.path.exists(parent_root_db):
            selected_db_path = parent_root_db

        # 3. If database file is found, copy and stream it
        if selected_db_path:
            shutil.copy2(selected_db_path, dest_path)
            return send_file(
                dest_path,
                as_attachment=True,
                download_name=backup_filename,
                mimetype='application/x-sqlite3'
            )
        else:
            # 4. Fallback: If still not found, list directory to help find it
            fallback_filename = f"error_{timestamp}.txt"
            dest_path = os.path.join(backup_dir, fallback_filename)
            with open(dest_path, "w") as f:
                f.write(f"Database file 'freight_crm.db' not found.\n")
                f.write(f"Looked in:\n1. {instance_db}\n2. {root_db}\n3. {parent_root_db}\n")
                
            return send_file(
                dest_path,
                as_attachment=True,
                download_name=fallback_filename,
                mimetype='text/plain'
            )
            
    except Exception as e:
        flash(f"Backup transfer sequence broken: {str(e)}", "danger")
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
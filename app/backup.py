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
import json
from datetime import datetime
from flask import current_app, flash, redirect, url_for, send_file
from app.backup import backup_bp
from app.models import db  # Ensure this points to your project's db instance

@backup_bp.route("/create", methods=["GET", "POST"])
def create():
    try:
        # 1. Setup backup directory
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.json"
        dest_path = os.path.join(backup_dir, backup_filename)

        # 2. Extract database tables dynamically
        backup_data = {}
        
        # Get all table names from SQLAlchemy metadata
        for table_name in db.metadata.tables.keys():
            try:
                # Query all rows from the table
                result = db.session.execute(db.select(db.metadata.tables[table_name])).fetchall()
                # Convert rows to dictionaries
                backup_data[table_name] = [dict(row._mapping) for row in result]
            except Exception as table_err:
                backup_data[table_name] = f"Error reading table: {str(table_err)}"

        # 3. Write data to a clean JSON file
        # Converting datetime objects to string to avoid JSON encoding errors
        def datetime_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError("Type not serializable")

        with open(dest_path, "w") as f:
            json.dump(backup_data, f, indent=4, default=datetime_serializer)

        # 4. Stream the JSON backup file straight to browser
        return send_file(
            dest_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/json'
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
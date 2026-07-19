import os
import json
from datetime import datetime, date
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory,
    send_file,
    current_app,
    request,
)

from flask_login import (
    login_required,
    current_user,
)

from sqlalchemy import DateTime, Date

from app.models import db
from app.services.backup_service import (
    create_backup,
    backup_history,
    database_info,
)

# ==========================================================
# Blueprint
# ==========================================================

backup_bp = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup",
)

# ==========================================================
# Helpers
# ==========================================================

def admin_only():
    return getattr(current_user, "role", "") == "admin"


def universal_serializer(obj):
    """
    Converts unsupported objects to JSON safely.
    """

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Decimal):
        return float(obj)

    return str(obj)


# ==========================================================
# Backup Dashboard
# ==========================================================

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


# ==========================================================
# Create Backup
# ==========================================================

@backup_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():

    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    try:

        backup_dir = os.path.join(
            current_app.root_path,
            "backups"
        )

        os.makedirs(
            backup_dir,
            exist_ok=True
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = f"backup_{timestamp}.json"

        file_path = os.path.join(
            backup_dir,
            filename,
        )

        backup_data = {}

        # Backup every table dynamically
        for table_name in db.metadata.tables.keys():

            table = db.metadata.tables[table_name]

            try:

                rows = db.session.execute(
                    db.select(table)
                ).fetchall()

                backup_data[table_name] = [
                    dict(row._mapping)
                    for row in rows
                ]

            except Exception as e:

                backup_data[table_name] = {
                    "error": str(e)
                }

        with open(file_path, "w", encoding="utf-8") as f:

            json.dump(
                backup_data,
                f,
                indent=4,
                default=universal_serializer,
            )

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/json",
        )

    except Exception as e:

        flash(
            f"Backup failed: {str(e)}",
            "danger",
        )

        return redirect(
            url_for("backup.index")
        )


# ==========================================================
# Automatic Backup
# ==========================================================

@backup_bp.route("/auto")
@login_required
def auto_backup():

    if not admin_only():
        return "Unauthorized", 403

    try:

        create_backup()

        return "Backup Created", 200

    except Exception as e:

        return str(e), 500


# ==========================================================
# Download Backup
# ==========================================================

@backup_bp.route("/download/<filename>")
@login_required
def download(filename):

    if not admin_only():
        return redirect(
            url_for("dashboard")
        )

    folder = os.path.join(
        current_app.root_path,
        "backups",
    )

    return send_from_directory(
        folder,
        filename,
        as_attachment=True,
    )


# ==========================================================
# Delete Backup
# ==========================================================

@backup_bp.route("/delete/<filename>")
@login_required
def delete(filename):

    if not admin_only():
        return redirect(
            url_for("dashboard")
        )

    file_path = os.path.join(
        current_app.root_path,
        "backups",
        filename,
    )

    if os.path.exists(file_path):

        os.remove(file_path)

        flash(
            "Backup deleted successfully.",
            "success",
        )

    else:

        flash(
            "Backup file not found.",
            "danger",
        )

    return redirect(
        url_for("backup.index")
    )


# ==========================================================
# Restore Backup
# ==========================================================
# PART 2 STARTS FROM HERE

@backup_bp.route("/restore", methods=["POST"])
@login_required
def restore():

    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("backup.index"))

    try:

        # --------------------------------------------------
        # Validate upload
        # --------------------------------------------------

        if "backup_file" not in request.files:
            flash("No backup file selected.", "danger")
            return redirect(url_for("backup.index"))

        file = request.files["backup_file"]

        if file.filename == "":
            flash("Please choose a backup file.", "danger")
            return redirect(url_for("backup.index"))

        if not file.filename.lower().endswith(".json"):
            flash("Only JSON backup files are supported.", "danger")
            return redirect(url_for("backup.index"))

        file_data = json.load(file)

        # --------------------------------------------------
        # DELETE ORDER
        # Child tables first
        # --------------------------------------------------

        delete_order = [

            "shipment_stages",
            "shipment_documents",
            "shipments",
            "quotations",
            "enquiries",
            "clients",
            "tasks",
            "notifications",
            "backup_logs",
            "users",

        ]

        for table_name in delete_order:

            if table_name not in db.metadata.tables:
                continue

            table = db.metadata.tables[table_name]

            db.session.execute(table.delete())

        db.session.flush()

        # --------------------------------------------------
        # RESTORE ORDER
        # Parent tables first
        # --------------------------------------------------

        restore_order = [

            "users",
            "clients",
            "enquiries",
            "quotations",
            "shipments",
            "shipment_documents",
            "shipment_stages",
            "tasks",
            "notifications",
            "backup_logs",

        ]

        for table_name in restore_order:

            if table_name not in db.metadata.tables:
                continue

            rows = file_data.get(table_name)

            if not isinstance(rows, list):
                continue

            table = db.metadata.tables[table_name]

            for row in rows:

                cleaned_row = {}

                for column in table.columns:

                    column_name = column.name

                    if column_name not in row:
                        continue

                    value = row[column_name]

                    if value is None:
                        cleaned_row[column_name] = None
                        continue

                    # DateTime
                    if isinstance(column.type, DateTime):

                        if isinstance(value, str):

                            try:
                                value = datetime.fromisoformat(value)
                            except Exception:
                                pass

                    # Date
                    elif isinstance(column.type, Date):

                        if isinstance(value, str):

                            try:
                                value = datetime.fromisoformat(value).date()
                            except Exception:
                                pass

                    cleaned_row[column_name] = value

                db.session.execute(
                    table.insert().values(**cleaned_row)
                )

        db.session.commit()

        flash(
            "Database restored successfully.",
            "success",
        )

    except Exception as e:

        db.session.rollback()

        current_app.logger.exception(e)

        flash(
            f"Restore failed : {str(e)}",
            "danger",
        )

    return redirect(url_for("backup.index"))
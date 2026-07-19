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
    current_app,
    send_file,
    request
)
from flask_login import (
    login_required,
    current_user,
)
from sqlalchemy import DateTime, Date, text
from app.models import db

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

    backup_dir = os.path.join(current_app.root_path, 'backups')
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.startswith('backup_') and f.endswith('.json'):
                fpath = os.path.join(backup_dir, f)
                backups.append({
                    'filename': f,
                    'created': datetime.fromtimestamp(os.path.getctime(fpath)).strftime("%Y-%m-%d %H:%M:%S"),
                    'size': f"{os.path.getsize(fpath) / 1024:.1f} KB"
                })

    return render_template(
        "backup/index.html",
        backups=backups,
    )


@backup_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    try:
        # 1. Setup backup directory
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.json"
        dest_path = os.path.join(backup_dir, backup_filename)

        # 2. Correct table order (parents first)
        table_order = [
            "users",
            "clients",
            "enquiries",
            "quotations",
            "shipments",
            "shipment_milestones",
            "shipment_documents",
            "shipment_customs_clearances",
            "shipment_closures",
            "shipment_party_details",
            "shipment_tasks",
            "client_tasks",
            "client_activities",
            "client_notes",
            "client_attachments",
            "client_pipeline_history",
            "client_status_history",
            "client_audit_logs",
            "support_tickets",
            "support_messages",
            "backup_logs",
            "settings",
            "client_portal_users",
        ]

        # 3. Extract database tables dynamically
        backup_data = {}
        for table_name in table_order:
            if table_name in db.metadata.tables:
                try:
                    table = db.metadata.tables[table_name]
                    result = db.session.execute(table.select()).fetchall()
                    backup_data[table_name] = [dict(row._mapping) for row in result]
                except Exception as table_err:
                    backup_data[table_name] = f"Error reading table: {str(table_err)}"

        # 4. Smart Serializer
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

        # 5. Stream the file directly to the browser
        return send_file(
            dest_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/json'
        )

    except Exception as e:
        flash(f"Backup creation failed: {str(e)}", "danger")
        return redirect(url_for("backup.index"))


@backup_bp.route("/download/<filename>")
@login_required
def download(filename):
    if not admin_only():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    folder = os.path.join(current_app.root_path, "backups")
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

    file_path = os.path.join(current_app.root_path, "backups", filename)

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
        if 'backup_file' not in request.files:
            flash("No file part found", "danger")
            return redirect(url_for("backup.index"))

        file = request.files['backup_file']
        if file.filename == '':
            flash("No selected file", "danger")
            return redirect(url_for("backup.index"))

        if not file.filename.endswith('.json'):
            flash("Invalid file format. Please upload a valid .json backup file.", "danger")
            return redirect(url_for("backup.index"))

        file_data = json.load(file)

        # CORRECT restore order (parent tables first, children last)
        restore_order = [
            "users",
            "clients",
            "enquiries",
            "quotations",
            "shipments",
            "shipment_milestones",
            "shipment_documents",
            "shipment_customs_clearances",
            "shipment_closures",
            "shipment_party_details",
            "shipment_tasks",
            "client_tasks",
            "client_activities",
            "client_notes",
            "client_attachments",
            "client_pipeline_history",
            "client_status_history",
            "client_audit_logs",
            "support_tickets",
            "support_messages",
            "backup_logs",
            "settings",
            "client_portal_users",
        ]

        # Disable foreign key checks for PostgreSQL
        db.session.execute(text("SET session_replication_role = 'replica';"))

        # Clear all tables in reverse order (children first)
        for table_name in reversed(restore_order):
            if table_name in db.metadata.tables:
                table = db.metadata.tables[table_name]
                db.session.execute(table.delete())

        # Restore data in correct order
        for table_name in restore_order:
            rows = file_data.get(table_name, [])
            if table_name in db.metadata.tables and isinstance(rows, list):
                table = db.metadata.tables[table_name]
                for row in rows:
                    cleaned_row = {}
                    for col_name, value in row.items():
                        if col_name in table.columns:
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
                        else:
                            cleaned_row[col_name] = value

                    db.session.execute(table.insert().values(**cleaned_row))

        # Re-enable foreign key checks
        db.session.execute(text("SET session_replication_role = 'origin';"))

        db.session.commit()
        flash("Database restored successfully! Please restart the application.", "success")

    except Exception as e:
        db.session.rollback()
        try:
            db.session.execute(text("SET session_replication_role = 'origin';"))
            db.session.commit()
        except:
            pass
        flash(f"Recovery failed: {str(e)}", "danger")

    return redirect(url_for("backup.index"))
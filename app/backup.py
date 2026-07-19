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
from sqlalchemy import DateTime, Date
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
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.json"
        dest_path = os.path.join(backup_dir, backup_filename)

        # CORRECT table order - parents first, children last
        table_order = [
            "users",
            "settings",
            "backup_logs",
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
            "client_portal_users",
        ]

        backup_data = {}
        for table_name in table_order:
            if table_name in db.metadata.tables:
                try:
                    table = db.metadata.tables[table_name]
                    result = db.session.execute(table.select()).fetchall()
                    backup_data[table_name] = [dict(row._mapping) for row in result]
                except Exception as table_err:
                    backup_data[table_name] = f"Error reading table: {str(table_err)}"

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

        # CORRECT restore order - parent tables first, children last
        # This ensures foreign keys exist before referencing them
        restore_order = [
            "users",                        # No FK dependencies
            "settings",                     # No FK
            "backup_logs",                  # No FK
            "clients",                      # FK: users (assigned_to_id, created_by_id)
            "enquiries",                    # FK: clients, users
            "quotations",                   # FK: enquiries, users
            "shipments",                    # FK: enquiries, quotations, clients, users
            "shipment_milestones",          # FK: shipments
            "shipment_documents",           # FK: shipments
            "shipment_customs_clearances",  # FK: shipments
            "shipment_closures",            # FK: shipments
            "shipment_party_details",       # FK: quotations, enquiries, users
            "shipment_tasks",               # FK: shipments
            "client_tasks",                 # FK: clients, users
            "client_activities",            # FK: clients, users
            "client_notes",                 # FK: clients, users
            "client_attachments",           # FK: clients
            "client_pipeline_history",      # FK: clients, users
            "client_status_history",        # FK: clients, users
            "client_audit_logs",            # FK: clients, users
            "support_tickets",              # FK: clients
            "support_messages",             # FK: support_tickets
            "client_portal_users",          # FK: clients
        ]

        # Clear all tables in reverse order (children first to avoid FK violations)
        for table_name in reversed(restore_order):
            if table_name in db.metadata.tables:
                table = db.metadata.tables[table_name]
                db.session.execute(table.delete())

        # Restore data in correct order (parents first)
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

        db.session.commit()
        flash("Database restored successfully! Please restart the application.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Recovery failed: {str(e)}", "danger")

    return redirect(url_for("backup.index"))
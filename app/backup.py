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

        # Get all tables from metadata in dependency order
        table_order = []
        for table_name in db.metadata.sorted_tables:
            table_order.append(table_name.name)

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

        # Get tables in reverse dependency order for deletion
        # and forward order for insertion
        sorted_tables = [t.name for t in db.metadata.sorted_tables]

        # Clear all tables in reverse order (children first)
        for table_name in reversed(sorted_tables):
            if table_name in db.metadata.tables:
                table = db.metadata.tables[table_name]
                try:
                    db.session.execute(table.delete())
                except Exception as del_err:
                    flash(f"Warning: Could not clear table {table_name}: {str(del_err)}", "warning")

        # Restore data in correct order (parents first)
        restored_count = {}
        skipped_columns = {}

        for table_name in sorted_tables:
            rows = file_data.get(table_name, [])
            if table_name not in db.metadata.tables:
                continue

            if not isinstance(rows, list):
                flash(f"Warning: Invalid data for table {table_name}, skipping", "warning")
                continue

            table = db.metadata.tables[table_name]
            actual_columns = set(table.columns.keys())

            # Track skipped columns for this table
            table_skipped = set()

            for row in rows:
                cleaned_row = {}
                for col_name, value in row.items():
                    # Skip columns that don't exist in current database schema
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

                # Only insert if we have valid columns
                if cleaned_row:
                    try:
                        db.session.execute(table.insert().values(**cleaned_row))
                    except Exception as insert_err:
                        flash(f"Warning: Could not insert row into {table_name}: {str(insert_err)}", "warning")
                        continue

            restored_count[table_name] = len(rows)
            if table_skipped:
                skipped_columns[table_name] = list(table_skipped)

        db.session.commit()

        # Build success message
        msg = f"Database restored successfully! {sum(restored_count.values())} total rows restored."
        if skipped_columns:
            skip_msg = "Skipped columns (old schema): " + ", ".join(
                [f"{t}.{c}" for t, cols in skipped_columns.items() for c in cols]
            )
            flash(msg + " " + skip_msg, "success")
        else:
            flash(msg, "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Recovery failed: {str(e)}", "danger")

    return redirect(url_for("backup.index"))
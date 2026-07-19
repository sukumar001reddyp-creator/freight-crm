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
from sqlalchemy import DateTime, Date
from app.models import db

backup_bp = Blueprint(
    "backup",
    __name__,
    url_prefix="/backup"
)

logger = logging.getLogger(__name__)


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

        table_order = [t.name for t in db.metadata.sorted_tables]

        backup_data = {}
        for table_name in table_order:
            if table_name in db.metadata.tables:
                try:
                    table = db.metadata.tables[table_name]
                    result = db.session.execute(table.select()).fetchall()
                    backup_data[table_name] = [dict(row._mapping) for row in result]
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
        logger.info(f"Database has tables: {sorted_tables}")

        matching_tables = [t for t in sorted_tables if t in file_data]
        logger.info(f"Matching tables: {matching_tables}")

        if not matching_tables:
            flash("No matching tables found in backup!", "danger")
            return redirect(url_for("backup.index"))

        # Clear tables in reverse order
        for table_name in reversed(sorted_tables):
            if table_name in db.metadata.tables and table_name in file_data:
                table = db.metadata.tables[table_name]
                try:
                    result = db.session.execute(table.delete())
                    logger.info(f"Cleared table {table_name}: {result.rowcount} rows deleted")
                except Exception as del_err:
                    logger.error(f"Could not clear {table_name}: {del_err}")

        # Restore data in correct order with batch commits
        total_rows = 0
        skipped_columns = {}

        for table_name in sorted_tables:
            if table_name not in file_data:
                continue

            rows = file_data[table_name]
            if not isinstance(rows, list):
                logger.warning(f"Table {table_name}: invalid data type {type(rows)}")
                continue

            table = db.metadata.tables[table_name]
            actual_columns = set(table.columns.keys())

            logger.info(f"Restoring {table_name}: {len(rows)} rows")

            table_skipped = set()
            table_inserted = 0

            for i, row in enumerate(rows):
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

                        # Batch commit every 100 rows to avoid memory issues
                        if total_rows % 100 == 0:
                            db.session.commit()
                            logger.info(f"Batch commit at {total_rows} rows")

                    except Exception as insert_err:
                        logger.error(f"Insert failed {table_name} row {i}: {insert_err}")
                        continue

            if table_skipped:
                skipped_columns[table_name] = list(table_skipped)

            logger.info(f"Table {table_name}: {table_inserted}/{len(rows)} rows inserted")

        # Final commit
        db.session.commit()
        logger.info(f"Restore complete: {total_rows} total rows")

        msg = f"Database restored! {total_rows} rows restored."
        if skipped_columns:
            skip_details = ", ".join([f"{t}: {', '.join(cols)}" for t, cols in skipped_columns.items()])
            msg += f" Skipped columns: {skip_details}"

        flash(msg, "success")

    except Exception as e:
        db.session.rollback()
        logger.exception("Restore failed")
        flash(f"Recovery failed: {str(e)}", "danger")

    return redirect(url_for("backup.index"))
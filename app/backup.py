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
        backup_dir = os.path.join(current_app.root_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Render లో ఉండే మెయిన్ రూట్ పాత్స్ ని డిక్లేర్ చేస్తున్నాం
        possible_paths = [
            os.path.join(current_app.instance_path, 'freight_crm.db'),
            os.path.join(current_app.root_path, 'freight_crm.db'),
            os.path.abspath(os.path.join(current_app.root_path, '..', 'freight_crm.db')),
            '/opt/render/project/src/instance/freight_crm.db',
            '/opt/render/project/src/freight_crm.db'
        ]
        
        selected_db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                selected_db_path = path
                break

        # 2. ఒకవేళ దొరికితే .db డౌన్‌లోడ్ అవుతుంది
        if selected_db_path:
            backup_filename = f"backup_{timestamp}.db"
            dest_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(selected_db_path, dest_path)
            return send_file(
                dest_path,
                as_attachment=True,
                download_name=backup_filename,
                mimetype='application/x-sqlite3'
            )
        
        # 3. దొరకకపోతే, సర్వర్ లో అసలు ఏమేం ఫైల్స్ ఉన్నాయో లిస్ట్ మొత్తం టెక్స్ట్ ఫైల్ లా ఇస్తుంది
        else:
            fallback_filename = f"debug_{timestamp}.txt"
            dest_path = os.path.join(backup_dir, fallback_filename)
            
            with open(dest_path, "w") as f:
                f.write("DATABASE NOT FOUND ANYWHERE!\n\n")
                f.write(f"Current Working Directory: {os.getcwd()}\n")
                f.write(f"Root Path: {current_app.root_path}\n\n")
                f.write("Files in Project Directory:\n")
                
                # సర్వర్ రూట్ లో ఉన్న ఫైల్స్ ని స్కాన్ చేస్తుంది
                try:
                    for root, dirs, files in os.walk(os.getcwd()):
                        # లోతైన లూప్స్ లేకుండా పైపైన వెతుకుతుంది
                        level = root.replace(os.getcwd(), '').count(os.sep)
                        if level < 2: 
                            f.write(f"{'  ' * level}[Dir] {os.path.basename(root)}/\n")
                            for file in files:
                                if file.endswith('.db'):
                                    f.write(f"{'  ' * (level+1)} FOUND DB: {file} inside {root}\n")
                                f.write(f"{'  ' * (level+1)}{file}\n")
                except Exception as walk_err:
                    f.write(f"Walk error: {str(walk_err)}")
                    
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
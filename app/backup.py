import os

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_from_directory,
    request,
    current_app,
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

    return getattr(
        current_user,
        "role",
        ""
    ) == "admin"


@backup_bp.route("/")
@login_required
def index():

    if not admin_only():

        flash(
            "Access denied.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "backup/index.html",
        backups=backup_history(),
        db_info=database_info(),
    )


@backup_bp.route("/create")
@login_required
def create():

    if not admin_only():
        flash(
            "Access denied.",
            "danger"
        )
        return redirect(
            url_for("dashboard")
        )

    try:

        create_backup()

        flash(
            "Database backup created successfully.",
            "success"
        )

    except Exception as e:

        flash(
            str(e),
            "danger"
        )

    return redirect(
        url_for("backup.index")
    )


@backup_bp.route("/auto")
def auto_backup():

    token = current_app.config.get(
        "SECRET_KEY"
    )

    #request_token = request.args.get(
     #   "token"
    #)

    #if request_token != token:
        #return "Unauthorized", 401

    try:

        create_backup()

        return "Backup Created", 200

    except Exception as e:

        return str(e), 500

@backup_bp.route("/download/<filename>")
@login_required
def download(filename):

    if not admin_only():
        return redirect(
            url_for("dashboard")
        )

    from flask import current_app

    folder = os.path.join(
        current_app.root_path,
        "backups"
)

    return send_from_directory(
        folder,
        filename,
        as_attachment=True
    )

@backup_bp.route("/restore/<filename>")
@login_required
def restore(filename):

    if not admin_only():
        return redirect(
            url_for("dashboard")
        )

    try:

        restore_backup(filename)

        flash(
            "Database restored successfully. Please restart the application.",
            "success"
        )

    except Exception as e:

        flash(
            str(e),
            "danger"
        )

    return redirect(
        url_for("backup.index")
    )

@backup_bp.route("/delete/<filename>")
@login_required
def delete(filename):

    if not admin_only():
        return redirect(url_for("dashboard"))

    from flask import current_app

    file_path = os.path.join(
        current_app.root_path,
        "backups",
        filename
    )

    if os.path.exists(file_path):
        os.remove(file_path)
        flash(
            "Backup deleted successfully.",
            "success"
        )
    else:
        flash(
            "Backup file not found.",
            "danger"
        )

    return redirect(
        url_for("backup.index")
    )
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Settings
from app import db

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

def admin_only():
    if getattr(current_user, "role", "") != "admin":
        abort(403)
@settings_bp.route("/")
@login_required
def index():
    admin_only()
    return redirect(url_for("settings.general"))

@settings_bp.route("/general", methods=["GET", "POST"])
@login_required
def general():
    admin_only()
    # Fetch settings, if not exists create default
    settings_data = Settings.query.first()
    if not settings_data:
        settings_data = Settings(id=1)
        db.session.add(settings_data)
        db.session.commit()

    if request.method == "POST":
        settings_data.app_env = request.form.get("app_env")
        settings_data.base_currency = request.form.get("base_currency")
        settings_data.alert_email = request.form.get("alert_email")
        db.session.commit()
        flash("Settings updated successfully!", "success")
        return redirect(url_for("settings.general"))

    return render_template("settings/index.html", active_tab="general", settings=settings_data)

@settings_bp.route("/update-maintenance", methods=["POST"])
@login_required
def update_maintenance():
    admin_only()
    settings_data = Settings.query.first()
    if settings_data:
        settings_data.maintenance = (request.form.get("maintenance_mode") == "on")
        db.session.commit()
    return redirect(url_for("settings.general"))

@settings_bp.route("/workflow", methods=["GET", "POST"])
@login_required
def workflow():
    admin_only()

    settings_data = Settings.query.first()

    if request.method == "POST":
        flash("Workflow settings updated successfully!", "success")
        return redirect(url_for("settings.workflow"))

    return render_template(
        "settings/index.html",
        active_tab="workflow",
        settings=settings_data
    )


@settings_bp.route("/roles")
@login_required
def roles():
    admin_only()

    settings_data = Settings.query.first()

    return render_template(
        "settings/index.html",
        active_tab="roles",
        settings=settings_data
    )
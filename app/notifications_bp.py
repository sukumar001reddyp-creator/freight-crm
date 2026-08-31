from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

from datetime import datetime, timezone, timedelta

@notifications_bp.route("/")
@login_required
def notification_list():
    # సరిగ్గా గడచిన 7 రోజులలో వచ్చిన నోటిఫికేషన్లను మాత్రమే ఫిల్టర్ చేయడం
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    notifications = Notification.query.filter(
        Notification.created_at >= seven_days_ago
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template("notifications/list.html", notifications=notifications)
    
@notifications_bp.route("/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_as_read(notif_id):
    notif = db.get_or_404(Notification, notif_id)
    notif.is_read = True
    db.session.commit()
    return jsonify({"success": True})

@notifications_bp.route("/clear-all", methods=["POST"])
@login_required
def clear_all():
    Notification.query.delete()
    db.session.commit()
    return redirect(url_for("notifications.notification_list"))
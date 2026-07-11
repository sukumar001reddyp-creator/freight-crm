from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from app import db
from app.models import (
    Shipment,
    ShipmentMilestone,
)

portal_bp = Blueprint(
    "portal",
    __name__,
    url_prefix=""
)


# =====================================================
# HOME
# =====================================================

@portal_bp.route("/")
def home():
    return redirect(
        url_for("portal.track")
    )


# =====================================================
# TRACK PAGE
# =====================================================

@portal_bp.route("/track", methods=["GET"])
def track():

    return render_template(
        "portal/track.html"
    )


# =====================================================
# SEARCH SHIPMENT
# =====================================================

@portal_bp.route("/track", methods=["POST"])
def track_search():

    shipment_reference = (
        request.form.get(
            "tracking_number",
            ""
        )
        .strip()
        .upper()
    )

    if not shipment_reference:

        flash(
            "Please enter your Shipment Reference.",
            "warning"
        )

        return redirect(
            url_for("portal.track")
        )

    shipment = Shipment.query.filter_by(
        shipment_reference=shipment_reference
    ).first()

    if shipment is None:

        return render_template(
            "portal/not_found.html",
            shipment_reference=shipment_reference,
        )

    return redirect(
        url_for(
            "portal.shipment",
            shipment_id=shipment.id,
        )
    )


# =====================================================
# SHIPMENT DETAILS
# =====================================================

@portal_bp.route("/shipment/<int:shipment_id>")
def shipment(shipment_id):

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )

    milestones = (
        ShipmentMilestone.query
        .filter_by(
            shipment_id=shipment.id
        )
        .order_by(
            ShipmentMilestone.completed_at.asc()
        )
        .all()
    )

    return render_template(
        "portal/shipment.html",
        shipment=shipment,
        milestones=milestones,
    )
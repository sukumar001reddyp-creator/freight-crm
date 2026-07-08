# =========================================================
# SHIPMENTS MODULE
#
# Workflow:
# Approved Quotation -> Shipment
# =========================================================

from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)

from flask_login import (
    login_required,
    current_user,
)
from app import db
from app.models import (
    Shipment,
    Quotation,
    ShipmentMilestone,
)


# =========================================================
# BLUEPRINT
# =========================================================

shipments_bp = Blueprint(
    "shipments",
    __name__,
    url_prefix="/shipments"
)


# =========================================================
# AUTO SHIPMENT REFERENCE GENERATOR
#
# Examples:
# SHP-2026-000001
# SHP-2026-000002
# =========================================================

def generate_shipment_reference():

    current_year = datetime.now().year

    prefix = (
        f"SHP-{current_year}-"
    )

    last_shipment = (
        db.session.execute(
            db.select(Shipment)
            .where(
                Shipment.shipment_reference.like(
                    f"{prefix}%"
                )
            )
            .order_by(
                Shipment.id.desc()
            )
        )
        .scalars()
        .first()
    )

    if not last_shipment:

        next_number = 1

    else:

        try:
            last_number = int(
                last_shipment
                .shipment_reference
                .split("-")[-1]
            )

            next_number = (
                last_number + 1
            )

        except (
            ValueError,
            IndexError
        ):
            next_number = 1

    return (
        f"{prefix}"
        f"{next_number:06d}"
    )


# =========================================================
# SHIPMENT LIST
# URL: /shipments/
#
# Purpose:
# Database lo unna shipments ni newest-first order lo
# display chestundi.
# =========================================================

@shipments_bp.route("/")
@login_required
def shipment_list():

    shipments = (
        db.session.execute(
            db.select(Shipment)
            .order_by(
                Shipment.created_at.desc()
            )
        )
        .scalars()
        .all()
    )

    return render_template(
        "shipments/list.html",
        shipments=shipments
    )
    # =========================================================
# CONVERT APPROVED QUOTATION TO SHIPMENT
#
# URL:
# /shipments/convert/<quotation_id>
#
# POST only
#
# Workflow:
# Approved Quotation
#       ↓
# Validate
#       ↓
# Create Shipment
#       ↓
# Enquiry status = converted
#       ↓
# Commit both in one transaction
# =========================================================

@shipments_bp.route(
    "/convert/<int:quotation_id>",
    methods=["POST"]
)
@login_required
def convert_from_quotation(quotation_id):

    # -----------------------------------------
    # LOAD QUOTATION
    # -----------------------------------------

    quotation = db.get_or_404(
        Quotation,
        quotation_id
    )

    enquiry = quotation.enquiry


    # -----------------------------------------
    # SAFETY CHECK:
    # ONLY APPROVED QUOTATION CAN CONVERT
    # -----------------------------------------

    if quotation.status != "approved":

        flash(
            (
                f"Quotation "
                f"{quotation.quotation_number} "
                f"must be approved before conversion."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )


    # -----------------------------------------
    # SAFETY CHECK:
    # QUOTATION ALREADY CONVERTED?
    # -----------------------------------------

    existing_by_quotation = (
        db.session.execute(
            db.select(Shipment)
            .where(
                Shipment.quotation_id
                == quotation.id
            )
        )
        .scalars()
        .first()
    )

    if existing_by_quotation:

        flash(
            (
                f"Quotation "
                f"{quotation.quotation_number} "
                f"was already converted to shipment "
                f"{existing_by_quotation.shipment_reference}."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "shipments.shipment_list"
            )
        )


    # -----------------------------------------
    # SAFETY CHECK:
    # ENQUIRY ALREADY CONVERTED?
    # -----------------------------------------

    existing_by_enquiry = (
        db.session.execute(
            db.select(Shipment)
            .where(
                Shipment.enquiry_id
                == enquiry.id
            )
        )
        .scalars()
        .first()
    )

    if existing_by_enquiry:

        flash(
            (
                f"Enquiry "
                f"{enquiry.enquiry_reference} "
                f"was already converted to shipment "
                f"{existing_by_enquiry.shipment_reference}."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "shipments.shipment_list"
            )
        )


    # -----------------------------------------
    # CREATE SHIPMENT OBJECT
    #
    # Client, route, cargo and handler are
    # copied from original enquiry.
    # -----------------------------------------

    shipment = Shipment(

        shipment_reference=(
            generate_shipment_reference()
        ),

        enquiry_id=enquiry.id,

        quotation_id=quotation.id,

        client_id=enquiry.client_id,

        origin=enquiry.origin,

        destination=enquiry.destination,

        mode_of_shipment=(
            enquiry.mode_of_shipment
        ),

        cargo_description=(
            enquiry.cargo_description
        ),

        cargo_weight_volume=(
            enquiry.cargo_weight_volume
        ),

        shipment_status="active",

        handled_by_id=(
            enquiry.handled_by_id
        ),

        created_by_id=(
            current_user.id
        ),
    )


    # -----------------------------------------
    # UPDATE ORIGINAL ENQUIRY
    #
    # Converted enquiry should not return
    # to normal sales workflow.
    # -----------------------------------------

    enquiry.status = "converted"


    # -----------------------------------------
    # SAVE SHIPMENT + ENQUIRY STATUS
    # IN ONE TRANSACTION
    # -----------------------------------------

    try:

        db.session.add(
            shipment
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            (
                "Unable to convert quotation "
                "to shipment. Please try again."
            ),
            "danger"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )


    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    flash(
        (
            f"Shipment "
            f"{shipment.shipment_reference} "
            f"created successfully."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shipments.shipment_list"
        )
    )
    # =========================================================
# VIEW SHIPMENT
# URL: /shipments/<shipment_id>
#
# Purpose:
# Single shipment full details display chestundi.
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>"
)
@login_required
def view_shipment(shipment_id):

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )

    milestones = (
        db.session.execute(
            db.select(ShipmentMilestone)
            .where(
                ShipmentMilestone.shipment_id
                == shipment.id
            )
            .order_by(
                ShipmentMilestone.completed_at.asc()
            )
        )
        .scalars()
        .all()
    )

    completed_stages = {
        milestone.stage
        for milestone in milestones
    }

    next_stage = None

    for stage in SHIPMENT_STAGES:

        if stage not in completed_stages:
            next_stage = stage
            break

    stage_labels = {
        "booking_confirmed": "Booking Confirmed",
        "pickup": "Pickup",
        "origin_handling": "Origin Handling",
        "in_transit": "In Transit",
        "arrival": "Arrival",
        "customs_clearance": "Customs Clearance",
        "delivery": "Delivery",
        "closed": "Closed",
    }

    return render_template(
        "shipments/view.html",
        shipment=shipment,
        milestones=milestones,
        completed_stages=completed_stages,
        next_stage=next_stage,
        shipment_stages=SHIPMENT_STAGES,
        stage_labels=stage_labels,
    )
    # =========================================================
# SHIPMENT WORKFLOW STAGES
# =========================================================

SHIPMENT_STAGES = [
    "booking_confirmed",
    "pickup",
    "origin_handling",
    "in_transit",
    "arrival",
    "customs_clearance",
    "delivery",
    "closed",
]


# =========================================================
# COMPLETE NEXT SHIPMENT STAGE
#
# URL:
# /shipments/<shipment_id>/stage/<stage>
#
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/stage/<stage>",
    methods=["POST"]
)
@login_required
def complete_stage(
    shipment_id,
    stage
):

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )


    # -----------------------------------------
    # VALID STAGE CHECK
    # -----------------------------------------

    if stage not in SHIPMENT_STAGES:

        flash(
            "Invalid shipment workflow stage.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # ALREADY COMPLETED STAGES
    # -----------------------------------------

    completed_milestones = (
        db.session.execute(
            db.select(ShipmentMilestone)
            .where(
                ShipmentMilestone.shipment_id
                == shipment.id
            )
            .order_by(
                ShipmentMilestone.completed_at.asc()
            )
        )
        .scalars()
        .all()
    )

    completed_stages = {
        milestone.stage
        for milestone in completed_milestones
    }


    # -----------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------

    if stage in completed_stages:

        flash(
            "This shipment stage is already completed.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # STRICT ORDER CHECK
    #
    # Only next pending stage can complete.
    # -----------------------------------------

    next_stage = None

    for workflow_stage in SHIPMENT_STAGES:

        if workflow_stage not in completed_stages:

            next_stage = workflow_stage
            break


    if stage != next_stage:

        flash(
            (
                "Shipment stages must be completed "
                "in workflow order."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # CREATE MILESTONE
    # -----------------------------------------

    milestone = ShipmentMilestone(
        shipment_id=shipment.id,
        stage=stage,
        completed_by_id=current_user.id,
    )


    # -----------------------------------------
    # UPDATE SHIPMENT SUMMARY STATUS
    # -----------------------------------------

    if stage == "in_transit":

        shipment.shipment_status = (
            "in_transit"
        )

    elif stage == "delivery":

        shipment.shipment_status = (
            "delivered"
        )

    elif stage == "closed":

        shipment.shipment_status = (
            "closed"
        )

    else:

        shipment.shipment_status = (
            "active"
        )


    # -----------------------------------------
    # SAVE IN ONE TRANSACTION
    # -----------------------------------------

    try:

        db.session.add(
            milestone
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to update shipment stage.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    flash(
        (
            f"Shipment stage "
            f"{stage.replace('_', ' ').title()} "
            f"completed successfully."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shipments.view_shipment",
            shipment_id=shipment.id
        )
    )
    # =========================================================
# EDIT SHIPMENT
#
# URL:
# /shipments/<shipment_id>/edit
#
# Active shipments only.
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_shipment(shipment_id):

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )


    # -----------------------------------------
    # LOCK AFTER TRANSIT / DELIVERY / CLOSURE
    # -----------------------------------------

    if shipment.shipment_status in (
        "in_transit",
        "delivered",
        "closed",
    ):

        flash(
            (
                "This shipment can no longer be edited "
                "because operational movement has started."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # SAVE CHANGES
    # -----------------------------------------

    if request.method == "POST":

        origin = request.form.get(
            "origin",
            ""
        ).strip()

        destination = request.form.get(
            "destination",
            ""
        ).strip()

        cargo_description = request.form.get(
            "cargo_description",
            ""
        ).strip()

        cargo_weight_volume = request.form.get(
            "cargo_weight_volume",
            ""
        ).strip()


        # -------------------------------------
        # REQUIRED FIELD VALIDATION
        # -------------------------------------

        if not origin:

            flash(
                "Origin is required.",
                "danger"
            )

            return render_template(
                "shipments/edit.html",
                shipment=shipment
            )


        if not destination:

            flash(
                "Destination is required.",
                "danger"
            )

            return render_template(
                "shipments/edit.html",
                shipment=shipment
            )


        if not cargo_description:

            flash(
                "Cargo description is required.",
                "danger"
            )

            return render_template(
                "shipments/edit.html",
                shipment=shipment
            )


        # -------------------------------------
        # UPDATE ALLOWED FIELDS
        # -------------------------------------

        shipment.origin = origin

        shipment.destination = destination

        shipment.cargo_description = (
            cargo_description
        )

        shipment.cargo_weight_volume = (
            cargo_weight_volume or None
        )


        # -------------------------------------
        # SAVE
        # -------------------------------------

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update shipment.",
                "danger"
            )

            return render_template(
                "shipments/edit.html",
                shipment=shipment
            )


        flash(
            (
                f"Shipment "
                f"{shipment.shipment_reference} "
                f"updated successfully."
            ),
            "success"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # SHOW EDIT FORM
    # -----------------------------------------

    return render_template(
        "shipments/edit.html",
        shipment=shipment
    )
    # =========================================================
# UNDO LAST SHIPMENT STAGE
#
# URL:
# /shipments/<shipment_id>/undo-last-stage
#
# POST only
#
# Safety:
# - Latest completed milestone only delete chestundi
# - Shipment summary status recalculate chestundi
# - One step at a time back vastundi
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/undo-last-stage",
    methods=["POST"]
)
@login_required
def undo_last_stage(shipment_id):

    # -----------------------------------------
    # LOAD SHIPMENT
    # -----------------------------------------

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )


    # -----------------------------------------
    # FIND LAST COMPLETED MILESTONE
    # -----------------------------------------

    last_milestone = (
        db.session.execute(
            db.select(ShipmentMilestone)
            .where(
                ShipmentMilestone.shipment_id
                == shipment.id
            )
            .order_by(
                ShipmentMilestone.completed_at.desc(),
                ShipmentMilestone.id.desc()
            )
        )
        .scalars()
        .first()
    )


    # -----------------------------------------
    # NOTHING TO UNDO
    # -----------------------------------------

    if not last_milestone:

        flash(
            "No completed shipment stage to undo.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # SAVE STAGE NAME FOR SUCCESS MESSAGE
    # -----------------------------------------

    undone_stage = (
        last_milestone.stage
    )


    # -----------------------------------------
    # DELETE ONLY LAST MILESTONE
    # -----------------------------------------

    try:

        db.session.delete(
            last_milestone
        )

        # Flush delete first so remaining stages
        # query reflects current transaction state.
        db.session.flush()


        # -------------------------------------
        # LOAD REMAINING COMPLETED STAGES
        # -------------------------------------

        remaining_milestones = (
            db.session.execute(
                db.select(ShipmentMilestone)
                .where(
                    ShipmentMilestone.shipment_id
                    == shipment.id
                )
                .order_by(
                    ShipmentMilestone.completed_at.asc(),
                    ShipmentMilestone.id.asc()
                )
            )
            .scalars()
            .all()
        )

        remaining_stages = {
            milestone.stage
            for milestone in remaining_milestones
        }


        # -------------------------------------
        # RECALCULATE SHIPMENT SUMMARY STATUS
        #
        # closed      -> closed
        # delivery    -> delivered
        # in_transit  -> in_transit
        # otherwise   -> active
        # -------------------------------------

        if "closed" in remaining_stages:

            shipment.shipment_status = (
                "closed"
            )

        elif "delivery" in remaining_stages:

            shipment.shipment_status = (
                "delivered"
            )

        elif "in_transit" in remaining_stages:

            shipment.shipment_status = (
                "in_transit"
            )

        else:

            shipment.shipment_status = (
                "active"
            )


        # -------------------------------------
        # SAVE
        # -------------------------------------

        db.session.commit()


    except Exception:

        db.session.rollback()

        flash(
            "Unable to undo the last shipment stage.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )


    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    flash(
        (
            f"{undone_stage.replace('_', ' ').title()} "
            f"stage was undone successfully."
        ),
        "success"
    )

    return redirect(
        url_for(
            "shipments.view_shipment",
            shipment_id=shipment.id
        )
    )
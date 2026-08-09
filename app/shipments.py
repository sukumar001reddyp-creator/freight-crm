# =========================================================
# SHIPMENTS MODULE
#
# Workflow:
# Approved Quotation -> Shipment
# =========================================================

from datetime import datetime, date


from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
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
    ShipmentDocument,
    ShipmentCustomsClearance,
    ShipmentClosure,
    Client,
    User,
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
# SHIPMENT WORKFLOW STAGES
# =========================================================

SHIPMENT_STAGES = [
    "booked",
    "cargo_picked_up",
    "in_transit",
    "arrived_destination",
    "customs_clearance",
    "out_for_delivery",
    "delivered",
    "closed_completed",
]


    
# =========================================================
# CLIENT-OWNERSHIP VISIBILITY
# =========================================================

def is_admin_user():
    return getattr(current_user, "role", None) == "admin"


def is_sales_user():
    return getattr(current_user, "role", None) in {
        "sales",
        "sales_executive",
    }


def can_view_shipment(shipment):
    """
    Admin sees every shipment.
    Sales sees shipments belonging to clients assigned to them.
    """
    if is_admin_user():
        return True

    if is_sales_user():
        client = db.session.get(
            Client,
            shipment.client_id
        )
        return bool(
            client
            and client.assigned_to_id == current_user.id
        )

    return False


def get_visible_shipment_or_404(shipment_id):

    shipment = db.get_or_404(
        Shipment,
        shipment_id
    )

    if not can_view_shipment(shipment):
        from flask import abort
        abort(404)

    return shipment


def require_shipment_write_access():

    print("Role:", current_user.role)
    print("Is Admin:", is_admin_user())

    if not is_admin_user():
        from flask import abort
        abort(403)


# =========================================================
# WORKFLOW HELPERS
# =========================================================

def get_customs_clearance(shipment_id):

    return (
        db.session.execute(
            db.select(ShipmentCustomsClearance)
            .where(
                ShipmentCustomsClearance.shipment_id
                == shipment_id
            )
        )
        .scalars()
        .first()
    )


def get_effective_workflow_stages(shipment_id):

    """
    Customs Clearance is conditional.

    - No clearance record yet:
      keep Customs Clearance in the workflow so the user
      must explicitly record whether clearance is required.
    - Clearance Required = No:
      skip the Customs Clearance milestone.
    - Clearance Required = Yes:
      keep Customs Clearance in the workflow.
    """

    customs_clearance = get_customs_clearance(
        shipment_id
    )

    if (
        customs_clearance is not None
        and not customs_clearance.clearance_required
    ):

        return [
            stage
            for stage in SHIPMENT_STAGES
            if stage != "customs_clearance"
        ]

    return list(
        SHIPMENT_STAGES
    )


def get_shipment_summary_status(completed_stages):

    if "closed_completed" in completed_stages:
        return "closed"

    if "delivered" in completed_stages:
        return "delivered"

    if "in_transit" in completed_stages:
        return "in_transit"

    return "active"


def get_shipment_closure(shipment_id):

    return (
        db.session.execute(
            db.select(ShipmentClosure)
            .where(
                ShipmentClosure.shipment_id
                == shipment_id
            )
        )
        .scalars()
        .first()
    )


def shipment_is_closed(shipment_id):

    return get_shipment_closure(
        shipment_id
    ) is not None


# =========================================================
# AUTO SHIPMENT REFERENCE GENERATOR
# =========================================================

def generate_shipment_reference():

    current_year = datetime.now().year
    prefix = f"SHP-{current_year}-"

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

            next_number = last_number + 1

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
# =========================================================

@shipments_bp.route("/")
@login_required
def shipment_list():
    selected_search = request.args.get("search", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_mode = request.args.get("mode", "").strip()
    selected_client_id = request.args.get("client_id", "").strip()
    selected_handled_by_id = request.args.get("handled_by_id", "").strip()

    query = db.select(Shipment)

    if is_sales_user():
        query = (
            query
            .join(
                Client,
                Shipment.client_id == Client.id
            )
            .where(
                Client.assigned_to_id
                == current_user.id
            )
        )
    elif not is_admin_user():
        from flask import abort
        abort(403)

    if selected_search:
        query = query.where(
            (Shipment.shipment_reference.ilike(f"%{selected_search}%")) |
            (Shipment.origin.ilike(f"%{selected_search}%")) |
            (Shipment.destination.ilike(f"%{selected_search}%"))
        )

    if selected_status:
        query = query.where(Shipment.shipment_status == selected_status)

    if selected_mode:
        query = query.where(Shipment.mode_of_shipment == selected_mode)

    if selected_client_id:
        query = query.where(Shipment.client_id == int(selected_client_id))

    if selected_handled_by_id:
        query = query.where(Shipment.handled_by_id == int(selected_handled_by_id))

    shipments = (
        db.session.execute(
            query.order_by(
                Shipment.created_at.desc()
            )
        )
        .scalars()
        .all()
    )

    clients_list = db.session.execute(db.select(Client).where(Client.is_archived == False).order_by(Client.company_name)).scalars().all()
    
    from app.models import User
    users_list = db.session.execute(db.select(User).order_by(User.full_name)).scalars().all()

    return render_template(
        "shipments/list.html",
        shipments=shipments,
        clients_list=clients_list,
        users_list=users_list,
        selected_search=selected_search,
        selected_status=selected_status,
        selected_mode=selected_mode,
        selected_client_id=selected_client_id,
        selected_handled_by_id=selected_handled_by_id
    )


# =========================================================
# CONVERT APPROVED QUOTATION TO SHIPMENT
# URL: /shipments/convert/<quotation_id>
# POST only
# =========================================================

@shipments_bp.route(
    "/convert/<int:quotation_id>",
    methods=["POST"]
)
@login_required
def convert_from_quotation(quotation_id):

    require_shipment_write_access()

    quotation = db.get_or_404(
    Quotation,
    quotation_id
)

    enquiry = quotation.enquiry if quotation.enquiry_id else None

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

    from app.models import ShipmentPartyDetails

    party_details = (
        db.session.execute(
            db.select(ShipmentPartyDetails)
            .where(
                ShipmentPartyDetails.quotation_id
                == quotation.id
            )
        )
        .scalars()
        .first()
    )

    if not party_details:

        flash(
            (
                "Agent, Shipper and Consignee details "
                "must be completed before shipment conversion."
            ),
            "warning"
        )

        return redirect(
            url_for(
                "quotations.manage_party_details",
                quotation_id=quotation.id
            )
        )

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

    if enquiry:

        existing_by_enquiry = (
            db.session.execute(
                db.select(Shipment)
                .where(
                    Shipment.enquiry_id == enquiry.id
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

    shipment = Shipment(
        shipment_reference=generate_shipment_reference(),
        enquiry_id=enquiry.id if enquiry else None,
        quotation_id=quotation.id,
        client_id=(
            enquiry.client_id
            if enquiry
            else quotation.client_id
        ),
        other_client_name=(
            None
            if enquiry
            else quotation.other_client_name
        ),
        origin=enquiry.origin if enquiry else quotation.origin,
        destination=enquiry.destination if enquiry else quotation.destination,
        mode_of_shipment=enquiry.mode_of_shipment if enquiry else quotation.mode_of_shipment,
        cargo_description=enquiry.cargo_description if enquiry else quotation.cargo_description,
        cargo_weight_volume=enquiry.cargo_weight_volume if enquiry else quotation.cargo_weight_volume,
        shipment_status="active",
        current_stage="booked",
        handled_by_id=(
            enquiry.handled_by_id
            if enquiry
            else quotation.created_by_id
        ),
        created_by_id=current_user.id,
    )

    if enquiry:
        enquiry.status = "converted"

    default_documents = [
        ("booking_confirmation", "Booking Confirmation"),
        ("bill_of_lading_airway_bill", "Bill of Lading / Airway Bill"),
        ("commercial_invoice", "Commercial Invoice"),
        ("packing_list", "Packing List"),
        ("certificate_of_origin", "Certificate of Origin"),
        ("insurance_certificate", "Insurance Certificate"),
        ("customs_declaration", "Customs Declaration"),
        ("other_supporting_document", "Other Supporting Documents"),
    ]

    try:

        db.session.add(
            shipment
        )

        db.session.flush()

        for document_type, document_name in default_documents:

            shipment_document = ShipmentDocument(
                shipment_id=shipment.id,
                document_type=document_type,
                document_name=document_name,
                status="pending",
                created_by_id=current_user.id,
            )

            db.session.add(
                shipment_document
            )

        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to convert quotation to shipment.",
            "danger"
    )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
        )
    )

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
            "shipments.view_shipment",
            shipment_id=shipment.id
        )
    )


# =========================================================
# VIEW SHIPMENT
# URL: /shipments/<shipment_id>
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>"
)
@login_required
def view_shipment(shipment_id):

    shipment = get_visible_shipment_or_404(
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

    effective_stages = (
        get_effective_workflow_stages(
            shipment.id
        )
    )

    next_stage = None

    for stage in effective_stages:

        if stage not in completed_stages:
            next_stage = stage
            break

    stage_labels = {
        "booked": "Booked",
        "cargo_picked_up": "Cargo Picked Up",
        "in_transit": "In Transit",
        "arrived_destination": "Arrived at Destination",
        "customs_clearance": "Customs Clearance",
        "out_for_delivery": "Out for Delivery",
        "delivered": "Delivered",
        "closed_completed": "Closed / Completed",
    }

    documents = (
        db.session.execute(
            db.select(ShipmentDocument)
            .where(
                ShipmentDocument.shipment_id
                == shipment.id
            )
            .order_by(
                ShipmentDocument.id.asc()
            )
        )
        .scalars()
        .all()
    )

    customs_clearance = (
        db.session.execute(
            db.select(ShipmentCustomsClearance)
            .where(
                ShipmentCustomsClearance.shipment_id
                == shipment.id
            )
        )
        .scalars()
        .first()
    )

    shipment_closure = get_shipment_closure(
        shipment.id
    )

    return render_template(
        "shipments/view.html",
        shipment=shipment,
        milestones=milestones,
        completed_stages=completed_stages,
        next_stage=next_stage,
        shipment_stages=effective_stages,
        stage_labels=stage_labels,
        documents=documents,
        customs_clearance=customs_clearance,
        shipment_closure=shipment_closure,
    )


# =========================================================
# UPDATE SHIPMENT DOCUMENT STATUS
# URL: /shipments/<shipment_id>/documents/<document_id>/status
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/documents/<int:document_id>/status",
    methods=["POST"]
)
@login_required
def update_document_status(
    shipment_id,
    document_id
):

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )
    milestones = (
    db.session.execute(
        db.select(ShipmentMilestone)
        .where(
            ShipmentMilestone.shipment_id == shipment.id
        )
        .order_by(
            ShipmentMilestone.completed_at.asc()
        )
    )
    .scalars()
    .all()
)
    if shipment_is_closed(shipment.id) and current_user.role != "admin":

        flash(
            "Closed shipments can be modified only by an Admin.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    document = db.get_or_404(
        ShipmentDocument,
        document_id
    )

    if document.shipment_id != shipment.id:

        flash(
            "Shipment document does not belong to this shipment.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    valid_statuses = {
        "pending",
        "received",
        "not_applicable",
    }

    status = request.form.get(
        "status",
        ""
    ).strip().lower()

    remarks = request.form.get(
        "remarks",
        ""
    ).strip()

    if status not in valid_statuses:

        flash(
            "Invalid shipment document status.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    try:

        document.status = status
        document.remarks = (
            remarks or None
        )

        if status == "received":

            if document.received_at is None:
                document.received_at = datetime.now()

            document.received_by_id = current_user.id

        else:

            document.received_at = None
            document.received_by_id = None

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to update shipment document status.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    flash(
        (
            f"{document.document_name} status updated to "
            f"{status.replace('_', ' ').title()}."
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
# CREATE / UPDATE CUSTOMS CLEARANCE
# URL: /shipments/<shipment_id>/customs-clearance
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/customs-clearance",
    methods=["POST"]
)
@login_required
def update_customs_clearance(shipment_id):

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )

    if shipment_is_closed(shipment.id) and current_user.role != "admin":

        flash(
            "Closed shipments can be modified only by an Admin.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    clearance_required_value = request.form.get(
        "clearance_required",
        ""
    ).strip().lower()

    if clearance_required_value not in {
        "yes",
        "no",
    }:

        flash(
            "Please select whether customs clearance is required.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    clearance_required = (
        clearance_required_value == "yes"
    )

    valid_statuses = {
        "not_required",
        "pending",
        "in_process",
        "cleared",
        "held_query",
    }

    clearance_status = request.form.get(
        "clearance_status",
        ""
    ).strip().lower()

    clearing_agent_name = request.form.get(
        "clearing_agent_name",
        ""
    ).strip()

    clearance_date_value = request.form.get(
        "clearance_date",
        ""
    ).strip()

    remarks = request.form.get(
        "customs_remarks",
        ""
    ).strip()

    if not clearance_required:

        clearance_status = "not_required"
        clearing_agent_name = ""
        clearance_date_value = ""

    elif clearance_status not in valid_statuses - {
        "not_required",
    }:

        flash(
            "Please select a valid customs clearance status.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    clearance_date = None

    if clearance_date_value:

        try:

            clearance_date = datetime.strptime(
                clearance_date_value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Invalid customs clearance date.",
                "danger"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

        if clearance_date > date.today():

            flash(
                "Customs clearance date cannot be in the future.",
                "danger"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

    if (
        clearance_status == "cleared"
        and clearance_date is None
    ):

        flash(
            "Clearance date is required when status is Cleared.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    customs_clearance = (
        db.session.execute(
            db.select(ShipmentCustomsClearance)
            .where(
                ShipmentCustomsClearance.shipment_id
                == shipment.id
            )
        )
        .scalars()
        .first()
    )

    try:

        if customs_clearance is None:

            customs_clearance = ShipmentCustomsClearance(
                shipment_id=shipment.id,
                created_by_id=current_user.id,
            )

            db.session.add(
                customs_clearance
            )

        customs_clearance.clearance_required = (
            clearance_required
        )

        customs_clearance.clearance_status = (
            clearance_status
        )

        customs_clearance.clearing_agent_name = (
            clearing_agent_name or None
        )

        customs_clearance.clearance_date = (
            clearance_date
        )

        customs_clearance.remarks = (
            remarks or None
        )

        customs_clearance.updated_by_id = (
            current_user.id
        )

        if not clearance_required:

            existing_customs_milestone = (
                db.session.execute(
                    db.select(ShipmentMilestone)
                    .where(
                        ShipmentMilestone.shipment_id
                        == shipment.id,
                        ShipmentMilestone.stage
                        == "customs_clearance"
                    )
                )
                .scalars()
                .first()
            )

            if existing_customs_milestone is not None:

                db.session.delete(
                    existing_customs_milestone
                )

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to update customs clearance details.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    flash(
        "Customs clearance details updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "shipments.view_shipment",
            shipment_id=shipment.id
        )
    )


# =========================================================
# CLOSE SHIPMENT
# URL: /shipments/<shipment_id>/close
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/close",
    methods=["POST"]
)
@login_required
def close_shipment(shipment_id):
    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )

    existing_closure = get_shipment_closure(
        shipment.id
    )

    if (
        existing_closure is not None
        and current_user.role != "admin"
    ):

        flash(
            "Closed shipments can be modified only by an Admin.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    completed_stages = {
        stage
        for stage in db.session.execute(
            db.select(ShipmentMilestone.stage)
            .where(
                ShipmentMilestone.shipment_id
                == shipment.id
            )
        )
        .scalars()
        .all()
    }

    if "delivered" not in completed_stages:

        flash(
            "Shipment can be closed only after the Delivered stage is completed.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    valid_statuses = {
        "delivered",
        "completed",
        "closed",
    }

    closing_status = request.form.get(
        "closing_status",
        ""
    ).strip().lower()

    closing_notes = request.form.get(
        "closing_notes",
        ""
    ).strip()

    client_feedback = request.form.get(
        "client_feedback",
        ""
    ).strip()

    client_rating_value = request.form.get(
        "client_rating",
        ""
    ).strip()

    archive_confirmed = (
        request.form.get(
            "document_archive_confirmed"
        ) == "yes"
    )

    if closing_status not in valid_statuses:

        flash(
            "Please select a valid closing status.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    if not archive_confirmed:

        flash(
            "Document Archive Confirmation is required before closing the shipment.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    client_rating = None

    if client_rating_value:

        try:

            client_rating = int(
                client_rating_value
            )

        except ValueError:

            flash(
                "Client rating must be a number from 1 to 5.",
                "danger"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

        if client_rating not in {
            1,
            2,
            3,
            4,
            5,
        }:

            flash(
                "Client rating must be between 1 and 5.",
                "danger"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

    try:

        if existing_closure is None:

            shipment_closure = ShipmentClosure(
                shipment_id=shipment.id,
                closing_status=closing_status,
                closing_date=datetime.now(),
                closing_notes=closing_notes or None,
                document_archive_confirmed=True,
                client_feedback=client_feedback or None,
                client_rating=client_rating,
                closed_by_id=current_user.id,
                updated_by_id=current_user.id,
            )

            db.session.add(
                shipment_closure
            )

        else:

            shipment_closure = existing_closure
            shipment_closure.closing_status = (
                closing_status
            )
            shipment_closure.closing_notes = (
                closing_notes or None
            )
            shipment_closure.document_archive_confirmed = True
            shipment_closure.client_feedback = (
                client_feedback or None
            )
            shipment_closure.client_rating = (
                client_rating
            )
            shipment_closure.updated_by_id = (
                current_user.id
            )

        closed_milestone = (
            db.session.execute(
                db.select(ShipmentMilestone)
                .where(
                    ShipmentMilestone.shipment_id
                    == shipment.id,
                    ShipmentMilestone.stage
                    == "closed_completed"
                )
            )
            .scalars()
            .first()
        )

        if closed_milestone is None:

            closed_milestone = ShipmentMilestone(
                shipment_id=shipment.id,
                stage="closed_completed",
                completed_by_id=current_user.id,
            )

            db.session.add(
                closed_milestone
            )

        shipment.shipment_status = "closed"
        shipment.current_stage = "closed_completed"
        db.session.commit()
        db.session.refresh(shipment)

    except Exception:

        db.session.rollback()

        flash(
            "Unable to close the shipment.",
            "danger"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    flash(
        "Shipment closure details saved successfully.",
        "success"
    )

    return redirect(
        url_for(
            "shipments.view_shipment",
            shipment_id=shipment.id
        )
    )


# =========================================================
# COMPLETE NEXT SHIPMENT STAGE
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

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )

    if shipment_is_closed(shipment.id):

        flash(
            "This shipment is already closed.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    if stage == "closed_completed":

        flash(
            "Use the Shipment Closing form to complete the final stage.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

    effective_stages = (
        get_effective_workflow_stages(
            shipment.id
        )
    )

    if stage not in effective_stages:

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

    next_stage = None

    for workflow_stage in effective_stages:

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

    if stage == "customs_clearance":

        customs_clearance = get_customs_clearance(
            shipment.id
        )

        if customs_clearance is None:

            flash(
                (
                    "Record Customs Clearance details first "
                    "and confirm whether clearance is required."
                ),
                "warning"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

        if not customs_clearance.clearance_required:

            flash(
                (
                    "Customs Clearance is not required for "
                    "this shipment and is skipped automatically."
                ),
                "warning"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

        if customs_clearance.clearance_status != "cleared":

            flash(
                (
                    "Customs Clearance stage can be completed "
                    "only after clearance status is Cleared."
                ),
                "warning"
            )

            return redirect(
                url_for(
                    "shipments.view_shipment",
                    shipment_id=shipment.id
                )
            )

    milestone = ShipmentMilestone(
        shipment_id=shipment.id,
        stage=stage,
        completed_by_id=current_user.id,
    )

    prospective_completed_stages = (
        completed_stages | {stage}
    )

    shipment.shipment_status = (
        get_shipment_summary_status(
            prospective_completed_stages
        )
    )
    shipment.current_stage = stage

    try:

        db.session.add(
            milestone
        )

        db.session.commit()
        db.session.refresh(shipment)

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
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_shipment(shipment_id):

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )

    if (
        shipment_is_closed(shipment.id)
        and current_user.role != "admin"
    ):
        flash("Closed shipments can be edited only by an Admin.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))


    if request.method == "POST":

        origin = request.form.get("origin", "").strip()
        destination = request.form.get("destination", "").strip()
        cargo_description = request.form.get("cargo_description", "").strip()
        cargo_weight_volume = request.form.get("cargo_weight_volume", "").strip()
        
        etd_value = request.form.get("etd", "").strip()
        eta_value = request.form.get("eta", "").strip()

        if not origin:
            flash("Origin is required.", "danger")
            return render_template("shipments/edit.html", shipment=shipment)

        if not destination:
            flash("Destination is required.", "danger")
            return render_template("shipments/edit.html", shipment=shipment)

        if not cargo_description:
            flash("Cargo description is required.", "danger")
            return render_template("shipments/edit.html", shipment=shipment)

        etd = None
        eta = None
        
        try:
            if etd_value:
                etd = datetime.strptime(etd_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                etd = datetime.strptime(etd_value, "%Y-%m-%d")
            except ValueError:
                pass

        try:
            if eta_value:
                eta = datetime.strptime(eta_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            try:
                eta = datetime.strptime(eta_value, "%Y-%m-%d")
            except ValueError:
                pass

        shipment.origin = origin
        shipment.destination = destination
        shipment.cargo_description = cargo_description
        shipment.cargo_weight_volume = cargo_weight_volume or None
        shipment.etd = etd
        shipment.eta = eta

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Unable to update shipment.", "danger")
            return render_template("shipments/edit.html", shipment=shipment)

        flash(f"Shipment {shipment.shipment_reference} updated successfully.", "success")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    return render_template("shipments/edit.html", shipment=shipment)


# =========================================================
# UNDO LAST SHIPMENT STAGE
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/undo-last-stage",
    methods=["POST"]
)
@login_required
def undo_last_stage(shipment_id):

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(
        shipment_id
    )

    existing_closure = get_shipment_closure(
        shipment.id
    )

    if (
        existing_closure is not None
        and current_user.role != "admin"
    ):

        flash(
            "Closed shipments can be modified only by an Admin.",
            "warning"
        )

        return redirect(
            url_for(
                "shipments.view_shipment",
                shipment_id=shipment.id
            )
        )

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

    undone_stage = (
        last_milestone.stage
    )

    try:

        db.session.delete(
            last_milestone
        )

        if (
            undone_stage == "closed_completed"
            and existing_closure is not None
        ):

            db.session.delete(
                existing_closure
            )

        db.session.flush()

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

        shipment.shipment_status = (
            get_shipment_summary_status(
                remaining_stages
            )
        )
        if remaining_milestones:
            shipment.current_stage = remaining_milestones[-1].stage
        else:
            shipment.current_stage = "booked"

        shipment.shipment_status = get_shipment_summary_status(
            {
                milestone.stage
                for milestone in remaining_milestones
            }
        )

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


# =========================================================
# GLOBAL PUBLIC TRACKING INTERFACE
# URL: /shipments/track
# =========================================================

@shipments_bp.route("/track", methods=["GET", "POST"])
@login_required
def track_shipment():
    search_query = request.args.get("tracking_number", "").strip()
    mode_filter = request.args.get("mode", "").strip()
    shipment = None
    documents = []
    milestones = []
    
    if search_query:
        res = db.session.execute(
            db.select(Shipment)
            .where(
                (Shipment.shipment_reference == search_query) | 
                (Shipment.hbl_no == search_query)
            )
        ).scalars().first()
        
        if res:
            if mode_filter and res.mode_of_shipment != mode_filter:
                flash("The shipment does not match the selected transport mode.", "warning")
            elif can_view_shipment(res):
                shipment = res
                documents = db.session.execute(
                    db.select(ShipmentDocument)
                    .where(ShipmentDocument.shipment_id == shipment.id)
                    .order_by(ShipmentDocument.document_name)
                ).scalars().all()
                milestones = db.session.execute(
                    db.select(ShipmentMilestone)
                    .where(ShipmentMilestone.shipment_id == shipment.id)
                    .order_by(ShipmentMilestone.completed_at)
                ).scalars().all()
            else:
                flash("You do not have permission to track this shipment.", "danger")
        else:
            flash("No records match the provided HBL/Reference number.", "danger")
            
    return render_template(
        "shipments/track.html", 
        shipment=shipment, 
        search_query=search_query
        ,mode_filter=mode_filter
        ,documents=documents
        ,milestones=milestones
        ,shipment_stages=SHIPMENT_STAGES
    )


# =========================================================
# DOWNLOAD INDIVIDUAL SHIPMENT DOCUMENT ROUTE
# URL: /shipments/<shipment_id>/documents/<int:document_id>/download
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/documents/<int:document_id>/download"
)
@login_required
def download_shipment_document(shipment_id, document_id):
    shipment = get_visible_shipment_or_404(shipment_id)
    document = db.get_or_404(ShipmentDocument, document_id)

    if document.shipment_id != shipment.id:
        flash("Document not found in this shipment.", "danger")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    if not document.file_path:
        flash("No physical file attached to this document record.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    import os
    from flask import current_app
    full_path = os.path.join(current_app.root_path, document.file_path.lstrip("/"))

    if not os.path.exists(full_path):
        flash("File missing from server storage.", "danger")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    return send_file(
        full_path,
        as_attachment=True,
        download_name=document.original_filename or f"document_{document.id}"
    )

# =========================================================
# DELETE INDIVIDUAL SHIPMENT DOCUMENT FILE
# URL: /shipments/<shipment_id>/documents/<int:document_id>/delete-file
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/documents/<int:document_id>/delete-file",
    methods=["POST"]
)
@login_required
def delete_shipment_document_file(shipment_id, document_id):
    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(shipment_id)

    if shipment_is_closed(shipment.id) and current_user.role != "admin":
        flash("Closed shipments can be modified only by an Admin.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    document = db.get_or_404(ShipmentDocument, document_id)

    if document.shipment_id != shipment.id:
        flash("Shipment document does not belong to this shipment.", "danger")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    import os
    from flask import current_app

    try:
        if document.file_path:
            full_path = os.path.join(current_app.root_path, document.file_path.lstrip("/"))
            if os.path.exists(full_path):
                os.remove(full_path)

        document.file_path = None
        document.original_filename = None
        document.status = "pending"
        document.received_at = None
        document.received_by_id = None

        db.session.commit()
        flash(f"{document.document_name} file removed successfully.", "success")

    except Exception:
        db.session.rollback()
        flash("Unable to delete document file.", "danger")

    return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))


# =========================================================
# UPLOAD INDIVIDUAL SHIPMENT DOCUMENT
# URL: /shipments/<shipment_id>/documents/<int:document_id>/upload-individual
# POST only
# =========================================================

@shipments_bp.route(
    "/<int:shipment_id>/documents/<int:document_id>/upload-individual",
    methods=["POST"]
)
@login_required
def upload_individual_shipment_document(shipment_id, document_id):

    require_shipment_write_access()

    shipment = get_visible_shipment_or_404(shipment_id)

    if shipment_is_closed(shipment.id) and current_user.role != "admin":
        flash("Closed shipments can be modified only by an Admin.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    document = db.get_or_404(ShipmentDocument, document_id)

    if document.shipment_id != shipment.id:
        flash("Shipment document does not belong to this shipment.", "danger")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    file = request.files.get("document_file")

    if not file or file.filename == "":
        flash("Please select a valid document file to upload.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    import os
    from werkzeug.utils import secure_filename
    from flask import current_app

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "shipments",
        str(shipment.id)
    )
    os.makedirs(upload_folder, exist_ok=True)

    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".docx"}
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        flash("Invalid file format. Only PDF, JPG, JPEG, and DOCX are allowed.", "danger")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"{int(datetime.now().timestamp())}_{original_filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # ఇక్కడ ఫైల్ పాత్ మరియు ఒరిజినల్ నేమ్ క్లియర్‌గా సేవ్ అవుతాయి
        document.file_path = f"static/uploads/shipments/{shipment.id}/{unique_filename}"
        document.original_filename = original_filename
        document.status = "received"
        document.received_at = datetime.now()
        document.received_by_id = current_user.id

        db.session.commit()
        flash(f"{document.document_name} uploaded successfully.", "success")

    except Exception as e:
        db.session.rollback()
        flash("Unable to upload document file.", "danger")

    return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))


# =========================================================
# CREATE DIRECT SHIPMENT (WITH PARTY DETAILS)
# =========================================================

@shipments_bp.route("/create-direct", methods=["GET", "POST"])
@login_required
def create_direct_shipment():
    require_shipment_write_access()

    clients_list = db.session.execute(
        db.select(Client).where(Client.is_archived == False).order_by(Client.company_name)
    ).scalars().all()
    
    users_list = db.session.execute(db.select(User).order_by(User.full_name)).scalars().all()

    if request.method == "POST":
        client_id = request.form.get("client_id")
        other_client_name = request.form.get("other_client_name", "").strip()
        origin = request.form.get("origin", "").strip()
        destination = request.form.get("destination", "").strip()
        mode_of_shipment = request.form.get("mode_of_shipment", "").strip()
        currency = request.form.get("currency", "USD").strip()
        cargo_description = request.form.get("cargo_description", "").strip()
        cargo_weight_volume = request.form.get("cargo_weight_volume", "").strip()
        hbl_no = request.form.get("hbl_no", "").strip()
        shipping_line = request.form.get("shipping_line", "").strip()
        vessel = request.form.get("vessel", "").strip()
        container_no = request.form.get("container_no", "").strip()
        container_type = request.form.get("container_type", "").strip()
        volume = request.form.get("volume", "").strip()
        handled_by_id = request.form.get("handled_by_id")

        # Party details
        agent_name = request.form.get("agent_name", "").strip()
        agent_country = request.form.get("agent_country", "").strip()
        agent_contact_person = request.form.get("agent_contact_person", "").strip()
        agent_phone = request.form.get("agent_phone", "").strip()
        agent_email = request.form.get("agent_email", "").strip()
        agent_reference = request.form.get("agent_reference", "").strip()

        shipper_name = request.form.get("shipper_name", "").strip()
        shipper_contact_person = request.form.get("shipper_contact_person", "").strip()
        shipper_phone = request.form.get("shipper_phone", "").strip()
        shipper_email = request.form.get("shipper_email", "").strip()
        shipper_address = request.form.get("shipper_address", "").strip()

        consignee_name = request.form.get("consignee_name", "").strip()
        consignee_contact_person = request.form.get("consignee_contact_person", "").strip()
        consignee_phone = request.form.get("consignee_phone", "").strip()
        consignee_email = request.form.get("consignee_email", "").strip()
        consignee_address = request.form.get("consignee_address", "").strip()

        ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or "0.00")
        origin_charges = Decimal(request.form.get("origin_charges") or "0.00")
        destination_charges = Decimal(request.form.get("destination_charges") or "0.00")
        insurance_charges = Decimal(request.form.get("insurance_charges") or "0.00")
        other_surcharges = Decimal(request.form.get("other_surcharges") or "0.00")
        
        quotation_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges

        if not origin or not destination or not cargo_description:
            flash("Origin, Destination, and Cargo Description are required.", "danger")
            return render_template("shipments/create_direct.html", clients_list=clients_list, users_list=users_list)

        direct_quotation = Quotation(
            quotation_number=f"DIR-QUO-{int(datetime.now().timestamp())}",
            client_id=int(client_id) if client_id and client_id not in ("other", "others") else None,
            other_client_name=other_client_name if client_id in ("other", "others") else None,
            quotation_amount=quotation_amount,
            currency=currency,
            validity_date=date.today(),
            status="approved",
            origin=origin,
            destination=destination,
            mode_of_shipment=mode_of_shipment,
            cargo_description=cargo_description,
            cargo_weight_volume=cargo_weight_volume,
            created_by_id=current_user.id
        )
        db.session.add(direct_quotation)
        db.session.flush()

        shipment = Shipment(
            shipment_reference=generate_shipment_reference(),
            quotation_id=direct_quotation.id,
            client_id=int(client_id) if client_id and client_id not in ("other", "others") else None,
            other_client_name=other_client_name if client_id in ("other", "others") else None,
            origin=origin,
            destination=destination,
            mode_of_shipment=mode_of_shipment,
            cargo_description=cargo_description,
            cargo_weight_volume=cargo_weight_volume or None,
            shipment_status="active",
            current_stage="booked",
            hbl_no=hbl_no or None,
            shipping_line=shipping_line or None,
            vessel=vessel or None,
            container_no=container_no or None,
            container_type=container_type or "40HC",
            volume=volume or None,
            handled_by_id=int(handled_by_id) if handled_by_id else current_user.id,
            created_by_id=current_user.id,
        )

        try:
            db.session.add(shipment)
            db.session.flush()

            party_details = ShipmentPartyDetails(
                quotation_id=direct_quotation.id,
                created_by_id=current_user.id,
                agent_name=agent_name,
                agent_country=agent_country,
                agent_contact_person=agent_contact_person,
                agent_phone=agent_phone,
                agent_email=agent_email,
                agent_reference=agent_reference or None,
                shipper_name=shipper_name,
                shipper_contact_person=shipper_contact_person,
                shipper_phone=shipper_phone,
                shipper_address=shipper_address,
                consignee_name=consignee_name,
                consignee_contact_person=consignee_contact_person,
                consignee_phone=consignee_phone,
                consignee_address=consignee_address
            )
            if hasattr(party_details, 'shipper_email'):
                party_details.shipper_email = shipper_email
            if hasattr(party_details, 'consignee_email'):
                party_details.consignee_email = consignee_email

            db.session.add(party_details)

            default_documents = [
                ("booking_confirmation", "Booking Confirmation"),
                ("bill_of_lading_airway_bill", "Bill of Lading / Airway Bill"),
                ("commercial_invoice", "Commercial Invoice"),
                ("packing_list", "Packing List"),
                ("certificate_of_origin", "Certificate of Origin"),
                ("insurance_certificate", "Insurance Certificate"),
                ("customs_declaration", "Customs Declaration"),
                ("other_supporting_document", "Other Supporting Documents"),
            ]

            for document_type, document_name in default_documents:
                db.session.add(ShipmentDocument(
                    shipment_id=shipment.id,
                    document_type=document_type,
                    document_name=document_name,
                    status="pending",
                    created_by_id=current_user.id,
                ))

            db.session.commit()
            flash(f"Direct Shipment {shipment.shipment_reference} created successfully.", "success")
            return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))

        except Exception as e:
            db.session.rollback()
            flash("Unable to create direct shipment.", "danger")

    return render_template("shipments/create_direct.html", clients_list=clients_list, users_list=users_list)

@shipments_bp.route("/<int:shipment_id>/cancel", methods=["POST"])
@login_required
def cancel_shipment(shipment_id):
    require_shipment_write_access()
    shipment = get_visible_shipment_or_404(shipment_id)
    
    try:
        shipment.shipment_status = "cancelled"
        db.session.commit()
        flash(f"Shipment {shipment.shipment_reference} has been cancelled successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to cancel shipment.", "danger")
        
    return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))


@shipments_bp.route("/<int:shipment_id>/delete", methods=["POST"])
@login_required
def delete_shipment(shipment_id):
    require_shipment_write_access()
    shipment = get_visible_shipment_or_404(shipment_id)
    
    # Kevalam shipment status cancelled unte ne delete avtundi
    if shipment.shipment_status != "cancelled":
        flash("Only cancelled shipments can be deleted.", "warning")
        return redirect(url_for("shipments.view_shipment", shipment_id=shipment.id))
    
    try:
        db.session.execute(db.delete(ShipmentMilestone).where(ShipmentMilestone.shipment_id == shipment.id))
        db.session.execute(db.delete(ShipmentDocument).where(ShipmentDocument.shipment_id == shipment.id))
        db.session.execute(db.delete(ShipmentCustomsClearance).where(ShipmentCustomsClearance.shipment_id == shipment.id))
        db.session.execute(db.delete(ShipmentClosure).where(ShipmentClosure.shipment_id == shipment.id))
        
        db.session.delete(shipment)
        db.session.commit()
        flash("Cancelled shipment deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to delete shipment.", "danger")
        
    return redirect(url_for("shipments.shipment_list"))

import os
import pdfkit
from flask import render_template, make_response, url_for, current_app
from datetime import datetime, timezone
from flask_login import login_required
from app.models import Shipment

@shipments_bp.route('/<int:shipment_id>/download-pdf')
@login_required
def download_shipment_pdf(shipment_id):
    shipment = Shipment.query.get_or_404(shipment_id)
    
    # ఇక్కడ నేరుగా డేటాబేస్ నుంచి మైలురాళ్లు మరియు డాక్యుమెంట్లు క్వెరీ చేస్తున్నాం
    milestones = db.session.execute(
        db.select(ShipmentMilestone)
        .where(ShipmentMilestone.shipment_id == shipment.id)
        .order_by(ShipmentMilestone.completed_at.asc())
    ).scalars().all()

    documents = db.session.execute(
        db.select(ShipmentDocument)
        .where(ShipmentDocument.shipment_id == shipment.id)
        .order_by(ShipmentDocument.id.asc())
    ).scalars().all()

    customs = (
        db.session.execute(
            db.select(ShipmentCustomsClearance)
            .where(ShipmentCustomsClearance.shipment_id == shipment.id)
        )
        .scalars()
        .first()
    )
    
    closure = get_shipment_closure(shipment.id)

    # లోగోల అబ్సల్యూట్ పాత్స్
    logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
    logo_url = f"file:///{logo_path.replace('\\', '/')}"

    logo2_path = os.path.join(current_app.root_path, 'static', 'images', 'logo2.png')
    logo2_url = f"file:///{logo2_path.replace('\\', '/')}"

    current_time = datetime.now(timezone.utc)

    html_content = render_template(
        "shipments/pdf_template.html",
        shipment=shipment,
        milestones=milestones,
        documents=documents,
        customs=customs,
        closure=closure,
        logo_url=logo_url,
        logo2_url=logo2_url,
        now=current_time
    )

    options = {
        'page-size': 'A4',
        'margin-top': '10mm',
        'margin-right': '10mm',
        'margin-bottom': '10mm',
        'margin-left': '10mm',
        'enable-local-file-access': None,
        'encoding': 'UTF-8',
        'no-outline': None
    }

    if os.name == "nt":
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        pdf = pdfkit.from_string(html_content, False, configuration=config, options=options)
    else:
        pdf = pdfkit.from_string(html_content, False, options=options)

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename=Shipment_{shipment.shipment_reference}.pdf'

    return response
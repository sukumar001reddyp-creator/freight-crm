# =========================================================
# ENQUIRIES MODULE
# Document Section 4.1 — Step 1
# =========================================================

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
)

from app import db
from app.models import (
    Client,
    Enquiry,
    User,
)


# =========================================================
# BLUEPRINT
# =========================================================

enquiries_bp = Blueprint(
    "enquiries",
    __name__,
    url_prefix="/enquiries"
)


# =========================================================
# AUTO ENQUIRY REFERENCE GENERATOR
# Example:
# ENQ-2026-000001
# ENQ-2026-000002
# =========================================================

def generate_enquiry_reference():

    current_year = datetime.now().year

    prefix = (
        f"ENQ-{current_year}-"
    )

    last_enquiry = (
        db.session.execute(
            db.select(Enquiry)
            .where(
                Enquiry.enquiry_reference.like(
                    f"{prefix}%"
                )
            )
            .order_by(
                Enquiry.id.desc()
            )
        )
        .scalars()
        .first()
    )

    if not last_enquiry:

        next_number = 1

    else:

        try:
            last_number = int(
                last_enquiry
                .enquiry_reference
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
# ENQUIRY LIST
# URL: /enquiries/
#
# Purpose:
# Database lo unna enquiries ni newest-first order lo
# load chesi HTML page ki pampistundi.
# =========================================================

@enquiries_bp.route("/")
@login_required
def enquiry_list():

    # Database nunchi all enquiries load chestundi
    enquiries = (
        db.session.execute(
            db.select(Enquiry)
            .order_by(
                Enquiry.created_at.desc()
            )
        )
        .scalars()
        .all()
    )

    # Data ni HTML template ki pampistundi
    return render_template(
        "enquiries/list.html",
        enquiries=enquiries
    )
    # =========================================================
# CREATE NEW ENQUIRY
# URL: /enquiries/add
# GET  -> Form open chestundi
# POST -> Form data database lo save chestundi
# =========================================================

@enquiries_bp.route(
    "/add",
    methods=["GET", "POST"]
)
@login_required
def add_enquiry():

    # -----------------------------------------
    # DROPDOWN DATA
    # -----------------------------------------

    clients = (
        db.session.execute(
            db.select(Client)
            .where(
                Client.is_archived.is_(False)
            )
            .order_by(
                Client.company_name.asc()
            )
        )
        .scalars()
        .all()
    )

    users = (
        db.session.execute(
            db.select(User)
            .where(
                User.is_active_user.is_(True)
            )
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )

    # -----------------------------------------
    # FORM SUBMITTED
    # -----------------------------------------

    if request.method == "POST":

        client_id = request.form.get(
            "client_id",
            type=int
        )

        origin = request.form.get(
            "origin",
            ""
        ).strip()

        destination = request.form.get(
            "destination",
            ""
        ).strip()

        mode_of_shipment = request.form.get(
            "mode_of_shipment",
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

        handled_by_id = request.form.get(
            "handled_by_id",
            type=int
        )

        # -------------------------------------
        # REQUIRED FIELD VALIDATION
        # -------------------------------------

        if not all(
            [
                client_id,
                origin,
                destination,
                mode_of_shipment,
                cargo_description,
                handled_by_id,
            ]
        ):
            flash(
                "Please complete all required fields.",
                "danger"
            )

            return render_template(
                "enquiries/add.html",
                clients=clients,
                users=users
            )

        # -------------------------------------
        # SECURITY:
        # CLIENT MUST EXIST AND BE ACTIVE
        # -------------------------------------

        client = db.session.get(
            Client,
            client_id
        )

        if (
            not client
            or client.is_archived
        ):
            flash(
                "Please select a valid client.",
                "danger"
            )

            return render_template(
                "enquiries/add.html",
                clients=clients,
                users=users
            )

        # -------------------------------------
        # SECURITY:
        # HANDLED-BY USER MUST BE ACTIVE
        # -------------------------------------

        handled_by = db.session.get(
            User,
            handled_by_id
        )

        if (
            not handled_by
            or not handled_by.is_active_user
        ):
            flash(
                "Please select a valid staff owner.",
                "danger"
            )

            return render_template(
                "enquiries/add.html",
                clients=clients,
                users=users
            )

        # -------------------------------------
        # CREATE ENQUIRY OBJECT
        # -------------------------------------

        enquiry = Enquiry(
            enquiry_reference=(
                generate_enquiry_reference()
            ),
            client_id=client.id,
            origin=origin,
            destination=destination,
            mode_of_shipment=mode_of_shipment,
            cargo_description=cargo_description,
            cargo_weight_volume=(
                cargo_weight_volume or None
            ),
            handled_by_id=handled_by.id,
            status="open",
            created_by_id=current_user.id,
        )

        db.session.add(
            enquiry
        )

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create enquiry. Please try again.",
                "danger"
            )

            return render_template(
                "enquiries/add.html",
                clients=clients,
                users=users
            )

        flash(
            (
                f"Enquiry "
                f"{enquiry.enquiry_reference} "
                f"created successfully."
            ),
            "success"
        )

        return redirect(
            url_for(
                "enquiries.enquiry_list"
            )
        )

    # -----------------------------------------
    # GET REQUEST:
    # JUST OPEN THE FORM
    # -----------------------------------------

    return render_template(
        "enquiries/add.html",
        clients=clients,
        users=users
    )
    # =========================================================
# VIEW ENQUIRY DETAILS
# URL: /enquiries/<enquiry_id>
#
# Purpose:
# One enquiry record ni full details tho open chestundi.
# =========================================================

@enquiries_bp.route(
    "/<int:enquiry_id>"
)
@login_required
def view_enquiry(enquiry_id):

    enquiry = db.get_or_404(
        Enquiry,
        enquiry_id
    )

    return render_template(
        "enquiries/view.html",
        enquiry=enquiry
    )
# =========================================================
# UPDATE ENQUIRY STATUS
# URL: /enquiries/<enquiry_id>/status
#
# POST only:
# Detail page nunchi selected status ni save chestundi.
# =========================================================

@enquiries_bp.route(
    "/<int:enquiry_id>/status",
    methods=["POST"]
)
@login_required
def update_enquiry_status(enquiry_id):

    # Database nunchi enquiry record load
    enquiry = db.get_or_404(
        Enquiry,
        enquiry_id
    )

    # Form nunchi selected status receive
    new_status = request.form.get(
        "status",
        ""
    ).strip()

    # Manam allow chese statuses matrame
    allowed_statuses = {
        "open",
        "in_progress",
        "quoted",
        "closed",
    }

    # Invalid value manually send chesina reject
    if new_status not in allowed_statuses:

        flash(
            "Invalid enquiry status.",
            "danger"
        )

        return redirect(
            url_for(
                "enquiries.view_enquiry",
                enquiry_id=enquiry.id
            )
        )

    # New status enquiry object lo set
    enquiry.status = new_status

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to update enquiry status.",
            "danger"
        )

        return redirect(
            url_for(
                "enquiries.view_enquiry",
                enquiry_id=enquiry.id
            )
        )

    flash(
        "Enquiry status updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "enquiries.view_enquiry",
            enquiry_id=enquiry.id
        )
    )
    # =========================================================
# EDIT ENQUIRY
# URL: /enquiries/<enquiry_id>/edit
#
# GET:
# Existing enquiry data form lo chupistundi.
#
# POST:
# Updated enquiry data database lo save chestundi.
# =========================================================

@enquiries_bp.route(
    "/<int:enquiry_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_enquiry(enquiry_id):

    # -----------------------------------------
    # LOAD EXISTING ENQUIRY
    # -----------------------------------------

    enquiry = db.get_or_404(
        Enquiry,
        enquiry_id
    )

    # -----------------------------------------
    # LOAD ACTIVE CLIENTS FOR DROPDOWN
    # -----------------------------------------

    clients = (
        db.session.execute(
            db.select(Client)
            .where(
                Client.is_archived.is_(False)
            )
            .order_by(
                Client.company_name.asc()
            )
        )
        .scalars()
        .all()
    )

    # -----------------------------------------
    # LOAD ACTIVE USERS FOR DROPDOWN
    # -----------------------------------------

    users = (
        db.session.execute(
            db.select(User)
            .where(
                User.is_active_user.is_(True)
            )
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )

    # -----------------------------------------
    # FORM SUBMITTED
    # -----------------------------------------

    if request.method == "POST":

        client_id = request.form.get(
            "client_id",
            type=int
        )

        origin = request.form.get(
            "origin",
            ""
        ).strip()

        destination = request.form.get(
            "destination",
            ""
        ).strip()

        mode_of_shipment = request.form.get(
            "mode_of_shipment",
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

        handled_by_id = request.form.get(
            "handled_by_id",
            type=int
        )

        # -------------------------------------
        # REQUIRED FIELD VALIDATION
        # -------------------------------------

        if not all(
            [
                client_id,
                origin,
                destination,
                mode_of_shipment,
                cargo_description,
                handled_by_id,
            ]
        ):

            flash(
                "Please complete all required fields.",
                "danger"
            )

            return render_template(
                "enquiries/edit.html",
                enquiry=enquiry,
                clients=clients,
                users=users
            )

        # -------------------------------------
        # VALIDATE CLIENT
        # -------------------------------------

        client = db.session.get(
            Client,
            client_id
        )

        if (
            not client
            or client.is_archived
        ):

            flash(
                "Please select a valid client.",
                "danger"
            )

            return render_template(
                "enquiries/edit.html",
                enquiry=enquiry,
                clients=clients,
                users=users
            )

        # -------------------------------------
        # VALIDATE STAFF OWNER
        # -------------------------------------

        handled_by = db.session.get(
            User,
            handled_by_id
        )

        if (
            not handled_by
            or not handled_by.is_active_user
        ):

            flash(
                "Please select a valid staff owner.",
                "danger"
            )

            return render_template(
                "enquiries/edit.html",
                enquiry=enquiry,
                clients=clients,
                users=users
            )

        # -------------------------------------
        # UPDATE EXISTING RECORD
        #
        # Important:
        # New Enquiry create cheyyatledu.
        # Existing enquiry fields matrame
        # change chestunnam.
        # -------------------------------------

        enquiry.client_id = client.id

        enquiry.origin = origin

        enquiry.destination = destination

        enquiry.mode_of_shipment = (
            mode_of_shipment
        )

        enquiry.cargo_description = (
            cargo_description
        )

        enquiry.cargo_weight_volume = (
            cargo_weight_volume or None
        )

        enquiry.handled_by_id = (
            handled_by.id
        )

        # -------------------------------------
        # SAVE CHANGES
        # -------------------------------------

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update enquiry. Please try again.",
                "danger"
            )

            return render_template(
                "enquiries/edit.html",
                enquiry=enquiry,
                clients=clients,
                users=users
            )

        # -------------------------------------
        # SUCCESS
        # -------------------------------------

        flash(
            (
                f"Enquiry "
                f"{enquiry.enquiry_reference} "
                f"updated successfully."
            ),
            "success"
        )

        return redirect(
            url_for(
                "enquiries.view_enquiry",
                enquiry_id=enquiry.id
            )
        )

    # -----------------------------------------
    # GET REQUEST
    #
    # Existing data tho edit form open.
    # -----------------------------------------

    return render_template(
        "enquiries/edit.html",
        enquiry=enquiry,
        clients=clients,
        users=users
    )
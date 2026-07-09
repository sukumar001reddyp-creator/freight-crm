# =========================================================
# QUOTATIONS MODULE
#
# Document Section 4.2:
# Quotation & Approval Status
# =========================================================

from datetime import datetime
import os
import uuid
from decimal import (
    Decimal,
    InvalidOperation,
)

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from flask_login import (
    login_required,
    current_user,
)

from app import db
from app.models import (
    Quotation,
    Enquiry,
    ShipmentPartyDetails,
)


# =========================================================
# BLUEPRINT
# =========================================================

quotations_bp = Blueprint(
    "quotations",
    __name__,
    url_prefix="/quotations"
)


# =========================================================
# AUTO QUOTATION NUMBER GENERATOR
#
# Examples:
# QUO-2026-000001
# QUO-2026-000002
#
# Quotation remains linked separately to Enquiry through
# enquiry_id in the database.
# =========================================================
# =========================================================
# QUOTATION PDF UPLOAD HELPERS
#
# Document Section 4.2:
# Quotation document is optional.
#
# For this module:
# Only PDF files are allowed.
# =========================================================

QUOTATION_ALLOWED_EXTENSIONS = {
    "pdf",
}


def allowed_quotation_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in QUOTATION_ALLOWED_EXTENSIONS
    )


def get_quotation_upload_folder():

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "quotations"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    return upload_folder
def generate_quotation_number():

    current_year = datetime.now().year

    prefix = (
        f"QUO-{current_year}-"
    )

    last_quotation = (
        db.session.execute(
            db.select(Quotation)
            .where(
                Quotation.quotation_number.like(
                    f"{prefix}%"
                )
            )
            .order_by(
                Quotation.id.desc()
            )
        )
        .scalars()
        .first()
    )

    if not last_quotation:

        next_number = 1

    else:

        try:
            last_number = int(
                last_quotation
                .quotation_number
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
# QUOTATION LIST
# URL: /quotations/
#
# Newest quotations first.
# =========================================================

@quotations_bp.route("/")
@login_required
def quotation_list():

    quotations = (
        db.session.execute(
            db.select(Quotation)
            .order_by(
                Quotation.created_at.desc()
            )
        )
        .scalars()
        .all()
    )

    return render_template(
        "quotations/list.html",
        quotations=quotations
    )
    # =========================================================
# CREATE QUOTATION
# URL: /quotations/create/<enquiry_id>
#
# GET:
# Quotation form open chestundi.
#
# POST:
# Quotation ni enquiry ki link chesi save chestundi.
# New quotation default status = pending.
# =========================================================

@quotations_bp.route(
    "/create/<int:enquiry_id>",
    methods=["GET", "POST"]
)
@login_required
def create_quotation(enquiry_id):

    # -----------------------------------------
    # LOAD ENQUIRY
    # -----------------------------------------

    enquiry = db.get_or_404(
        Enquiry,
        enquiry_id
    )


    # -----------------------------------------
    # FORM SUBMITTED
    # -----------------------------------------

    if request.method == "POST":

        quotation_amount = request.form.get(
            "quotation_amount",
            ""
        ).strip()

        currency = request.form.get(
            "currency",
            ""
        ).strip().upper()

        validity_date_text = request.form.get(
            "validity_date",
            ""
        ).strip()


        # -------------------------------------
        # REQUIRED FIELD VALIDATION
        # -------------------------------------

        if not all(
            [
                quotation_amount,
                currency,
                validity_date_text,
            ]
        ):

            flash(
                "Please complete all required quotation fields.",
                "danger"
            )

            return render_template(
                "quotations/create.html",
                enquiry=enquiry
            )


        # -------------------------------------
        # VALIDATE AMOUNT
        #
        # Decimal use chestunnam because
        # quotation amount is money.
        # -------------------------------------

        try:
            amount_value = Decimal(
                quotation_amount
            )

            if amount_value <= 0:
                raise InvalidOperation

        except (
            InvalidOperation,
            ValueError
        ):

            flash(
                "Please enter a valid quotation amount.",
                "danger"
            )

            return render_template(
                "quotations/create.html",
                enquiry=enquiry
            )


        # -------------------------------------
        # VALIDATE CURRENCY
        # -------------------------------------

        allowed_currencies = {
            "USD",
            "KWD",
            "AED",
        }

        if currency not in allowed_currencies:

            flash(
                "Please select a valid currency.",
                "danger"
            )

            return render_template(
                "quotations/create.html",
                enquiry=enquiry
            )


        # -------------------------------------
        # VALIDATE VALIDITY DATE
        # HTML date format:
        # YYYY-MM-DD
        # -------------------------------------

        try:
            validity_date = datetime.strptime(
                validity_date_text,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Please enter a valid validity date.",
                "danger"
            )

            return render_template(
                "quotations/create.html",
                enquiry=enquiry
            )

                    # -------------------------------------
        # OPTIONAL QUOTATION PDF
        # -------------------------------------

        quotation_file = request.files.get(
            "quotation_document"
        )

        original_filename = None
        stored_filename = None
        relative_path = None
        absolute_path = None


        # -------------------------------------
        # VALIDATE PDF IF PROVIDED
        # -------------------------------------

        if (
            quotation_file
            and quotation_file.filename
        ):

            if not allowed_quotation_file(
                quotation_file.filename
            ):

                flash(
                    "Only PDF quotation documents are allowed.",
                    "danger"
                )

                return render_template(
                    "quotations/create.html",
                    enquiry=enquiry
                )


            # ---------------------------------
            # SAFE ORIGINAL FILE NAME
            # ---------------------------------

            original_filename = secure_filename(
                quotation_file.filename
            )

            if not original_filename:

                flash(
                    "Invalid quotation document filename.",
                    "danger"
                )

                return render_template(
                    "quotations/create.html",
                    enquiry=enquiry
                )


            # ---------------------------------
            # UNIQUE STORED FILE NAME
            # ---------------------------------

            stored_filename = (
                f"{uuid.uuid4().hex}.pdf"
            )


            # ---------------------------------
            # UPLOAD FOLDER
            # ---------------------------------

            upload_folder = (
                get_quotation_upload_folder()
            )

            absolute_path = os.path.join(
                upload_folder,
                stored_filename
            )


            # ---------------------------------
            # SAVE FILE
            # ---------------------------------

            try:
                quotation_file.save(
                    absolute_path
                )

            except Exception:

                flash(
                    "Unable to save quotation PDF.",
                    "danger"
                )

                return render_template(
                    "quotations/create.html",
                    enquiry=enquiry
                )


            # ---------------------------------
            # RELATIVE PATH FOR DATABASE
            # ---------------------------------

            relative_path = os.path.join(
                "uploads",
                "quotations",
                stored_filename
            ).replace("\\", "/")


        # -------------------------------------
        # CREATE QUOTATION OBJECT
        # -------------------------------------

        quotation = Quotation(
            quotation_number=(
                generate_quotation_number()
            ),
            enquiry_id=enquiry.id,
            quotation_amount=amount_value,
            currency=currency,
            validity_date=validity_date,

            document_original_filename=(
                original_filename
            ),
            document_stored_filename=(
                stored_filename
            ),
            document_file_path=(
                relative_path
            ),

            status="pending",
            created_by_id=current_user.id,
        )


        # -------------------------------------
        # UPDATE ENQUIRY WORKFLOW STATUS
        #
        # Quotation prepared against enquiry.
        # -------------------------------------

        enquiry.status = "quoted"


        # -------------------------------------
        # SAVE BOTH IN ONE TRANSACTION
        # -------------------------------------

        try:
            db.session.add(
                quotation
            )

            db.session.commit()

        except Exception as e:

            db.session.rollback()
            print(
    "QUOTATION CREATE ERROR:",
    repr(e),
    flush=True
)

            # If DB save failed after PDF was saved,
            # remove orphan file from disk.
            if (
                absolute_path
                and os.path.exists(
                    absolute_path
                )
            ):

                try:
                    os.remove(
                        absolute_path
                    )

                except OSError:
                    pass

            flash(
                "Unable to create quotation. Please try again.",
                "danger"
            )

            return render_template(
                "quotations/create.html",
                enquiry=enquiry
            )

        # -------------------------------------
        # SUCCESS
        # -------------------------------------

        flash(
            (
                f"Quotation "
                f"{quotation.quotation_number} "
                f"created successfully."
            ),
            "success"
        )

        return redirect(
            url_for(
                "quotations.quotation_list"
            )
        )


    # -----------------------------------------
    # GET REQUEST
    # -----------------------------------------

    return render_template(
        "quotations/create.html",
        enquiry=enquiry
    )
    # =========================================================
# VIEW QUOTATION
# URL: /quotations/<quotation_id>
#
# Purpose:
# Single quotation full details display chestundi.
# =========================================================

# =========================================================
# AGENT / SHIPPER / CONSIGNEE DETAILS
#
# Approved Quotation ->
# Party Details ->
# Shipment Conversion
#
# GET:
# - Existing details unte edit form
# - Lekapothe blank form
#
# POST:
# - Create or update one record per quotation
# =========================================================

@quotations_bp.route(
    "/<int:quotation_id>/party-details",
    methods=["GET", "POST"]
)
@login_required
def manage_party_details(quotation_id):

    # -----------------------------------------
    # LOAD QUOTATION
    # -----------------------------------------

    quotation = db.get_or_404(
        Quotation,
        quotation_id
    )


    # -----------------------------------------
    # ONLY APPROVED QUOTATIONS
    # -----------------------------------------

    if quotation.status != "approved":

        flash(
            (
                "Agent, shipper and consignee details "
                "can be added only after quotation approval."
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
    # LOAD EXISTING PARTY DETAILS
    # -----------------------------------------

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


    # -----------------------------------------
    # HANDLE FORM SUBMISSION
    # -----------------------------------------

    if request.method == "POST":

        # =====================================
        # AGENT DETAILS
        # =====================================

        agent_name = request.form.get(
            "agent_name",
            ""
        ).strip()

        agent_country = request.form.get(
            "agent_country",
            ""
        ).strip()

        agent_contact_person = request.form.get(
            "agent_contact_person",
            ""
        ).strip()

        agent_phone = request.form.get(
            "agent_phone",
            ""
        ).strip()

        agent_email = request.form.get(
            "agent_email",
            ""
        ).strip()

        agent_reference = request.form.get(
            "agent_reference",
            ""
        ).strip()


        # =====================================
        # SHIPPER DETAILS
        # =====================================

        shipper_name = request.form.get(
            "shipper_name",
            ""
        ).strip()

        shipper_address = request.form.get(
            "shipper_address",
            ""
        ).strip()

        shipper_contact_person = request.form.get(
            "shipper_contact_person",
            ""
        ).strip()

        shipper_phone = request.form.get(
            "shipper_phone",
            ""
        ).strip()


        # =====================================
        # CONSIGNEE DETAILS
        # =====================================

        consignee_name = request.form.get(
            "consignee_name",
            ""
        ).strip()

        consignee_address = request.form.get(
            "consignee_address",
            ""
        ).strip()

        consignee_contact_person = request.form.get(
            "consignee_contact_person",
            ""
        ).strip()

        consignee_phone = request.form.get(
            "consignee_phone",
            ""
        ).strip()


        # -------------------------------------
        # REQUIRED FIELD VALIDATION
        # -------------------------------------

        required_fields = {
            "Agent Name": agent_name,
            "Agent Country": agent_country,
            "Agent Contact Person": agent_contact_person,
            "Agent Phone": agent_phone,
            "Agent Email": agent_email,

            "Shipper Name": shipper_name,
            "Shipper Address": shipper_address,
            "Shipper Contact Person": shipper_contact_person,
            "Shipper Phone": shipper_phone,

            "Consignee Name": consignee_name,
            "Consignee Address": consignee_address,
            "Consignee Contact Person": consignee_contact_person,
            "Consignee Phone": consignee_phone,
        }

        missing_fields = [
            field_name
            for field_name, field_value
            in required_fields.items()
            if not field_value
        ]


        if missing_fields:

            flash(
                (
                    "Please complete all required fields: "
                    + ", ".join(missing_fields)
                ),
                "danger"
            )

            return render_template(
                "quotations/party_details.html",
                quotation=quotation,
                party_details=party_details,
            )


        # -------------------------------------
        # CREATE NEW RECORD IF NEEDED
        # -------------------------------------

        if party_details is None:

            party_details = ShipmentPartyDetails(
                quotation_id=quotation.id,
                enquiry_id=quotation.enquiry_id,
                created_by_id=current_user.id,
            )

            db.session.add(
                party_details
            )


        # -------------------------------------
        # UPDATE AGENT DETAILS
        # -------------------------------------

        party_details.agent_name = agent_name
        party_details.agent_country = agent_country
        party_details.agent_contact_person = (
            agent_contact_person
        )
        party_details.agent_phone = agent_phone
        party_details.agent_email = agent_email

        party_details.agent_reference = (
            agent_reference or None
        )


        # -------------------------------------
        # UPDATE SHIPPER DETAILS
        # -------------------------------------

        party_details.shipper_name = shipper_name
        party_details.shipper_address = shipper_address

        party_details.shipper_contact_person = (
            shipper_contact_person
        )

        party_details.shipper_phone = shipper_phone


        # -------------------------------------
        # UPDATE CONSIGNEE DETAILS
        # -------------------------------------

        party_details.consignee_name = consignee_name
        party_details.consignee_address = (
            consignee_address
        )

        party_details.consignee_contact_person = (
            consignee_contact_person
        )

        party_details.consignee_phone = (
            consignee_phone
        )


        # -------------------------------------
        # SAVE
        # -------------------------------------

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                (
                    "Unable to save shipment party details. "
                    "Please try again."
                ),
                "danger"
            )

            return render_template(
                "quotations/party_details.html",
                quotation=quotation,
                party_details=party_details,
            )


        # -------------------------------------
        # SUCCESS
        # -------------------------------------

        flash(
            (
                "Agent, shipper and consignee "
                "details saved successfully."
            ),
            "success"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )


    # -----------------------------------------
    # GET REQUEST
    # -----------------------------------------

    return render_template(
        "quotations/party_details.html",
        quotation=quotation,
        party_details=party_details,
    )
# =========================================================
# APPROVE QUOTATION
# URL: /quotations/<quotation_id>/approve
#
# POST only:
# - Pending quotation ni approve chestundi
# - Current logged-in user ni Approved By ga save chestundi
# - Approval date/time automatic ga save chestundi
# =========================================================

@quotations_bp.route(
    "/<int:quotation_id>/approve",
    methods=["POST"]
)
@login_required
def approve_quotation(quotation_id):

    # -----------------------------------------
    # LOAD QUOTATION
    # -----------------------------------------

    quotation = db.get_or_404(
        Quotation,
        quotation_id
    )


    # -----------------------------------------
    # ONLY PENDING CAN BE APPROVED
    # -----------------------------------------

    if quotation.status != "pending":

        flash(
            (
                f"Quotation "
                f"{quotation.quotation_number} "
                f"is already "
                f"{quotation.status}."
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
    # APPROVE
    # -----------------------------------------

    quotation.status = "approved"

    quotation.approved_by_id = (
        current_user.id
    )

    quotation.approved_at = (
        datetime.now()
    )

    # Rejection reason should remain empty
    quotation.rejection_reason = None


    # -----------------------------------------
    # SAVE
    # -----------------------------------------

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to approve quotation. Please try again.",
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
            f"Quotation "
            f"{quotation.quotation_number} "
            f"approved successfully."
        ),
        "success"
    )

    return redirect(
        url_for(
            "quotations.view_quotation",
            quotation_id=quotation.id
        )
    )


# =========================================================
# REJECT QUOTATION
# URL: /quotations/<quotation_id>/reject
#
# POST only:
# - Pending quotation ni reject chestundi
# - Rejection reason mandatory
# - Rejected quotation DB lo history ga remain avuthundi
# =========================================================

@quotations_bp.route(
    "/<int:quotation_id>/reject",
    methods=["POST"]
)
@login_required
def reject_quotation(quotation_id):

    # -----------------------------------------
    # LOAD QUOTATION
    # -----------------------------------------

    quotation = db.get_or_404(
        Quotation,
        quotation_id
    )


    # -----------------------------------------
    # ONLY PENDING CAN BE REJECTED
    # -----------------------------------------

    if quotation.status != "pending":

        flash(
            (
                f"Quotation "
                f"{quotation.quotation_number} "
                f"is already "
                f"{quotation.status}."
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
    # GET REJECTION REASON
    # -----------------------------------------

    rejection_reason = request.form.get(
        "rejection_reason",
        ""
    ).strip()


    # -----------------------------------------
    # REASON IS MANDATORY
    # -----------------------------------------

    if not rejection_reason:

        flash(
            "Rejection reason is required.",
            "danger"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )


    # -----------------------------------------
    # REJECT
    # -----------------------------------------

    quotation.status = "rejected"

    quotation.rejection_reason = (
        rejection_reason
    )

    # Approval fields must remain empty
    quotation.approved_by_id = None

    quotation.approved_at = None


    # -----------------------------------------
    # SAVE
    # -----------------------------------------

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to reject quotation. Please try again.",
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
            f"Quotation "
            f"{quotation.quotation_number} "
            f"rejected successfully."
        ),
        "success"
    )

    return redirect(
        url_for(
            "quotations.view_quotation",
            quotation_id=quotation.id
        )
    )
    # =========================================================
# VIEW / DOWNLOAD QUOTATION PDF
# URL: /quotations/<quotation_id>/document
# =========================================================

@quotations_bp.route(
    "/<int:quotation_id>/document"
)
@login_required
def quotation_document(quotation_id):

    quotation = db.get_or_404(
        Quotation,
        quotation_id
    )

    # No document attached
    if not quotation.document_stored_filename:

        flash(
            "No quotation document is attached.",
            "warning"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )

    upload_folder = (
        get_quotation_upload_folder()
    )

    file_path = os.path.join(
        upload_folder,
        quotation.document_stored_filename
    )

    # DB record exists but physical file missing
    if not os.path.isfile(file_path):

        flash(
            "Quotation document file was not found.",
            "danger"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )

    return send_from_directory(
        upload_folder,
        quotation.document_stored_filename,
        as_attachment=False,
        download_name=(
            quotation.document_original_filename
            or quotation.document_stored_filename
        )
    )
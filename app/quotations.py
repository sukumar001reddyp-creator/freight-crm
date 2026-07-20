# =========================================================
# QUOTATIONS MODULE - FULL CODE (UPDATED WITH 4.1 & 4.2)
# =========================================================

from datetime import datetime
import os
import uuid
from decimal import Decimal, InvalidOperation
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, current_app, send_from_directory
)
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db
from app.models import Client, Quotation, Enquiry, ShipmentPartyDetails
from app.sales_scope import (
    scope_quotations, get_enquiry_or_404, get_quotation_or_404,
)

quotations_bp = Blueprint("quotations", __name__, url_prefix="/quotations")

# --- హెల్పర్స్ ---
def allowed_quotation_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"

def get_quotation_upload_folder():
    upload_folder = os.path.join(current_app.root_path, "static", "uploads", "quotations")
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder

def generate_quotation_number():
    current_year = datetime.now().year
    prefix = f"QUO-{current_year}-"
    last_quotation = db.session.execute(
        db.select(Quotation).where(Quotation.quotation_number.like(f"{prefix}%")).order_by(Quotation.id.desc())
    ).scalars().first()
    
    next_number = int(last_quotation.quotation_number.split("-")[-1]) + 1 if last_quotation else 1
    return f"{prefix}{next_number:06d}"

# =========================================================
# CREATE QUOTATION (UPDATED WITH 4.1 & 4.2 + COST BREAKDOWN)
# =========================================================

# =========================================================
# CREATE QUOTATION - అప్‌డేటెడ్ ఫంక్షన్
# =========================================================

@quotations_bp.route("/create/<int:enquiry_id>", methods=["GET", "POST"])
@login_required
def create_quotation(enquiry_id):
    enquiry = get_enquiry_or_404(enquiry_id)

    if request.method == "POST":
        # 1. అన్ని కాస్ట్ ఫీల్డ్స్ తీసుకోవాలి
        ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or 0)
        origin_charges = Decimal(request.form.get("origin_charges") or 0)
        destination_charges = Decimal(request.form.get("destination_charges") or 0)
        insurance_charges = Decimal(request.form.get("insurance_charges") or 0)
        other_surcharges = Decimal(request.form.get("other_surcharges") or 0)
        
        # 2. ఆటోమేటిక్ గా టోటల్ కాలిక్యులేట్ చెయ్
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
        # ఇతర వివరాలు
        currency = request.form.get("currency")
        validity = request.form.get("validity_date")
        
        # Section 4.1: Shipment Details
        shipping_line = request.form.get("shipping_line_airline")
        no_containers = request.form.get("no_of_containers", type=int)
        container_type = request.form.get("container_type_quota")
        etd = datetime.strptime(request.form.get("etd"), "%Y-%m-%dT%H:%M") if request.form.get("etd") else None
        cutoff_doc = datetime.strptime(request.form.get("cutoff_date_documentation"), "%Y-%m-%dT%H:%M") if request.form.get("cutoff_date_documentation") else None
        cutoff_cargo = datetime.strptime(request.form.get("cutoff_date_cargo"), "%Y-%m-%dT%H:%M") if request.form.get("cutoff_date_cargo") else None
        free_time = request.form.get("free_time_days", type=int)
        transit_time = request.form.get("transit_time_days", type=int)
        incoterms = request.form.get("incoterms")
        hs_code = request.form.get("hs_code")
        
        # Section 4.2: Payment & Remarks
        payment_terms = request.form.get("payment_terms")
        remarks = request.form.get("remarks_terms")

        # Create Quotation
        quotation = Quotation(
            quotation_number=generate_quotation_number(),
            enquiry_id=enquiry.id,
            quotation_amount=total_amount, # ఇక్కడ కాలిక్యులేట్ చేసిన టోటల్ అమౌంట్ వేస్తున్నాం
            currency=currency,
            validity_date=datetime.strptime(validity, "%Y-%m-%d").date(),
            
            shipping_line_airline=shipping_line,
            no_of_containers=no_containers,
            container_type_quota=container_type,
            etd=etd,
            cutoff_date_documentation=cutoff_doc,
            cutoff_date_cargo=cutoff_cargo,
            free_time_days=free_time,
            transit_time_days=transit_time,
            incoterms=incoterms,
            hs_code=hs_code,
            
            payment_terms=payment_terms,
            remarks_terms=remarks,
            
            ocean_air_freight=ocean_air_freight,
            origin_charges=origin_charges,
            destination_charges=destination_charges,
            insurance_charges=insurance_charges,
            other_surcharges=other_surcharges,
            
            status="pending",
            created_by_id=current_user.id
        )
        
        enquiry.status = "quoted"
        db.session.add(quotation)
        db.session.commit()
        
        flash("Quotation created successfully!", "success")
        return redirect(url_for("quotations.quotation_list"))

    return render_template("quotations/create.html", enquiry=enquiry)

@quotations_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_direct_quotation():

    clients = Client.query.order_by(Client.company_name).all()

    if request.method == "POST":

        client = Client.query.get_or_404(
            request.form.get("client_id")
        )

        quotation = Quotation()

        quotation.client_id = client.id
        quotation.enquiry_id = None

        quotation.quotation_number = generate_quotation_number()

        quotation.currency = request.form.get("currency")
        quotation.validity_date = datetime.strptime(
            request.form.get("validity_date"),
            "%Y-%m-%d"
        ).date()

        quotation.shipping_line_airline = request.form.get("shipping_line_airline")
        quotation.no_of_containers = request.form.get("no_of_containers") or None
        quotation.container_type_quota = request.form.get("container_type_quota")
        quotation.etd = datetime.strptime(request.form.get("etd"), "%Y-%m-%dT%H:%M") if request.form.get("etd") else None
        quotation.cutoff_date_documentation = datetime.strptime(request.form.get("cutoff_date_documentation"), "%Y-%m-%dT%H:%M") if request.form.get("cutoff_date_documentation") else None
        quotation.cutoff_date_cargo = datetime.strptime(request.form.get("cutoff_date_cargo"), "%Y-%m-%dT%H:%M") if request.form.get("cutoff_date_cargo") else None
        quotation.free_time_days = request.form.get("free_time_days", type=int)
        quotation.transit_time_days = request.form.get("transit_time_days", type=int)
        
        quotation.incoterms = request.form.get("incoterms")
        quotation.hs_code = request.form.get("hs_code")

        quotation.payment_terms = request.form.get("payment_terms")
        quotation.remarks_terms = request.form.get("remarks_terms")

        quotation.ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or 0)

        quotation.origin_charges = Decimal(request.form.get("origin_charges") or 0)

        quotation.destination_charges = Decimal(request.form.get("destination_charges") or 0)

        quotation.insurance_charges = Decimal(request.form.get("insurance_charges") or 0)

        quotation.other_surcharges = Decimal(request.form.get("other_surcharges") or 0)

        quotation.quotation_amount = (
            quotation.ocean_air_freight
            + quotation.origin_charges
            + quotation.destination_charges
            + quotation.insurance_charges
            + quotation.other_surcharges
        )

        quotation.created_by_id = current_user.id

        db.session.add(quotation)
        db.session.commit()

        flash(
            "Direct quotation created successfully.",
            "success"
        )

        return redirect(
            url_for(
                "quotations.view_quotation",
                quotation_id=quotation.id
            )
        )

    return render_template(
        "quotations/create_direct.html",
        clients=clients
    )
# =========================================================
# REST OF THE FILE (unchanged - kept full)
# =========================================================

@quotations_bp.route("/")
@login_required
def quotation_list():
    quotations = (
        db.session.execute(
            scope_quotations(
                db.select(Quotation)
            )
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


# ... (All other routes like view_quotation, manage_party_details, approve, reject, download_pdf remain exactly the same)

# (I kept the rest of your file intact - only create_quotation updated)

# =========================================================
# VIEW QUOTATION
# =========================================================

@quotations_bp.route(
    "/<int:quotation_id>"
)
@login_required
def view_quotation(quotation_id):

    quotation = get_quotation_or_404(quotation_id)

    # ----------------------------------------- 
    # CHECK WHETHER ALREADY CONVERTED
    # -----------------------------------------

    from app.models import Shipment

    converted_shipment = (
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

    # ----------------------------------------- 
    # LOAD AGENT / SHIPPER / CONSIGNEE DETAILS
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

    return render_template(
        "quotations/view.html",
        quotation=quotation,
        converted_shipment=converted_shipment,
        party_details=party_details,
    )


# =========================================================
# AGENT / SHIPPER / CONSIGNEE DETAILS
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

    quotation = get_quotation_or_404(quotation_id)


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

    quotation = get_quotation_or_404(quotation_id)


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

    quotation = get_quotation_or_404(quotation_id)


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



from flask import make_response
import os
import pdfkit

@quotations_bp.route("/<int:quotation_id>/download")
@login_required
def download_quotation_pdf(quotation_id):
    quotation = get_quotation_or_404(quotation_id)

    html_content = render_template(
        "quotations/pdf_template.html",
        quotation=quotation
    )

    if os.name == "nt":
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        pdf = pdfkit.from_string(html_content, False, configuration=config)
    else:
        pdf = pdfkit.from_string(html_content, False)

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f'attachment; filename=Quotation_{quotation.quotation_number}.pdf'
    )

    return response

@quotations_bp.route("/<int:quotation_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    
    # కేవలం 'pending' క్వోటేషన్స్ మాత్రమే ఎడిట్ చేసేలా సెట్ చేద్దాం
    if quotation.status != "pending":
        flash("You can only edit pending quotations.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    if request.method == "POST":
        # 1. అన్ని కాస్ట్ ఫీల్డ్స్ తీసుకోవాలి
        ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or 0)
        origin_charges = Decimal(request.form.get("origin_charges") or 0)
        destination_charges = Decimal(request.form.get("destination_charges") or 0)
        insurance_charges = Decimal(request.form.get("insurance_charges") or 0)
        other_surcharges = Decimal(request.form.get("other_surcharges") or 0)
        
        # 2. ఆటోమేటిక్ గా టోటల్ కాలిక్యులేట్ చెయ్
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
        # 3. వాల్యూస్ అప్‌డేట్ చేయడం
        quotation.quotation_amount = total_amount
        quotation.ocean_air_freight = ocean_air_freight
        quotation.origin_charges = origin_charges
        quotation.destination_charges = destination_charges
        quotation.insurance_charges = insurance_charges
        quotation.other_surcharges = other_surcharges
        quotation.remarks_terms = request.form.get("remarks_terms")
        quotation.payment_terms = request.form.get("payment_terms")
        
        db.session.commit()
        flash("Quotation updated successfully!", "success")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    return render_template("quotations/edit.html", quotation=quotation)
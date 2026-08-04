# =========================================================
# QUOTATIONS MODULE - FULL CLEAN CODE
# =========================================================

from datetime import datetime
import os
import pdfkit
from decimal import Decimal
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, flash, current_app, make_response
)
from flask_login import login_required, current_user
from app import db
from app.models import Client, Quotation, Enquiry, ShipmentPartyDetails
from app.sales_scope import (
    scope_quotations, get_enquiry_or_404, get_quotation_or_404,
)

quotations_bp = Blueprint("quotations", __name__, url_prefix="/quotations")

def generate_quotation_number():
    current_year = datetime.now().year
    prefix = f"QUO-{current_year}-"
    last_quotation = db.session.execute(
        db.select(Quotation).where(Quotation.quotation_number.like(f"{prefix}%")).order_by(Quotation.id.desc())
    ).scalars().first()
    
    next_number = int(last_quotation.quotation_number.split("-")[-1]) + 1 if last_quotation else 1
    return f"{prefix}{next_number:06d}"

@quotations_bp.route("/create/<int:enquiry_id>", methods=["GET", "POST"])
@login_required
def create_quotation(enquiry_id):
    enquiry = get_enquiry_or_404(enquiry_id)

    if request.method == "POST":
        ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or 0)
        origin_charges = Decimal(request.form.get("origin_charges") or 0)
        destination_charges = Decimal(request.form.get("destination_charges") or 0)
        insurance_charges = Decimal(request.form.get("insurance_charges") or 0)
        other_surcharges = Decimal(request.form.get("other_surcharges") or 0)
        
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
        currency = request.form.get("currency")
        validity = request.form.get("validity_date")
        
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
        
        payment_terms = request.form.get("payment_terms")
        remarks = request.form.get("remarks_terms")

        quotation = Quotation(
            quotation_number=generate_quotation_number(),
            enquiry_id=enquiry.id,
            quotation_amount=total_amount,
            currency=currency,
            validity_date=datetime.strptime(validity, "%Y-%m-%d").date(),
            origin=enquiry.origin,
            destination=enquiry.destination,
            origin_port=enquiry.origin_port,
            destination_port=enquiry.destination_port,
            mode_of_shipment=enquiry.mode_of_shipment,
            cargo_description=enquiry.cargo_description,
            cargo_weight_volume=enquiry.cargo_weight_volume,
            incoterms=enquiry.incoterms,
            shipping_line_airline=shipping_line,
            no_of_containers=no_containers,
            container_type_quota=container_type,
            etd=etd,
            cutoff_date_documentation=cutoff_doc,
            cutoff_date_cargo=cutoff_cargo,
            free_time_days=free_time,
            transit_time_days=transit_time,
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
        client_id = request.form.get("client_id")
        other_client_name = request.form.get("other_client_name")

        quotation = Quotation()
        quotation.enquiry_id = None
        quotation.status = "pending"

        if client_id == "others":
            quotation.client_id = None
            quotation.other_client_name = other_client_name
        else:
            client = Client.query.get_or_404(client_id)
            quotation.client_id = client.id
            quotation.other_client_name = None

        quotation.quotation_number = generate_quotation_number()
        quotation.currency = request.form.get("currency")
        quotation.validity_date = datetime.strptime(request.form.get("validity_date"), "%Y-%m-%d").date()
        quotation.origin = request.form.get("origin")
        quotation.destination = request.form.get("destination")
        quotation.origin_port = request.form.get("origin_port")
        quotation.destination_port = request.form.get("destination_port")
        quotation.mode_of_shipment = request.form.get("mode_of_shipment")
        quotation.cargo_description = request.form.get("cargo_description")
        quotation.cargo_weight_volume = request.form.get("cargo_weight_volume")
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

        flash("Direct quotation created successfully.", "success")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    return render_template("quotations/create_direct.html", clients=clients)

@quotations_bp.route("/")
@login_required
def quotation_list():
    quotations = (
        db.session.execute(
            scope_quotations(db.select(Quotation).where(Quotation.is_deleted == False))
            .order_by(Quotation.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("quotations/list.html", quotations=quotations)

@quotations_bp.route("/<int:quotation_id>")
@login_required
def view_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    from app.models import Shipment
    converted_shipment = db.session.execute(db.select(Shipment).where(Shipment.quotation_id == quotation.id)).scalars().first()
    party_details = db.session.execute(db.select(ShipmentPartyDetails).where(ShipmentPartyDetails.quotation_id == quotation.id)).scalars().first()

    return render_template(
        "quotations/view.html",
        quotation=quotation,
        converted_shipment=converted_shipment,
        party_details=party_details,
    )

@quotations_bp.route("/<int:quotation_id>/party-details", methods=["GET", "POST"])
@login_required
def manage_party_details(quotation_id):
    quotation = get_quotation_or_404(quotation_id)

    if quotation.status != "approved":
        flash("Agent, shipper and consignee details can be added only after quotation approval.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    party_details = db.session.execute(db.select(ShipmentPartyDetails).where(ShipmentPartyDetails.quotation_id == quotation.id)).scalars().first()

    if request.method == "POST":
        agent_name = request.form.get("agent_name", "").strip()
        agent_country = request.form.get("agent_country", "").strip()
        agent_contact_person = request.form.get("agent_contact_person", "").strip()
        agent_phone = request.form.get("agent_phone", "").strip()
        agent_email = request.form.get("agent_email", "").strip()
        agent_reference = request.form.get("agent_reference", "").strip()

        shipper_name = request.form.get("shipper_name", "").strip()
        shipper_address = request.form.get("shipper_address", "").strip()
        shipper_contact_person = request.form.get("shipper_contact_person", "").strip()
        shipper_phone = request.form.get("shipper_phone", "").strip()

        consignee_name = request.form.get("consignee_name", "").strip()
        consignee_address = request.form.get("consignee_address", "").strip()
        consignee_contact_person = request.form.get("consignee_contact_person", "").strip()
        consignee_phone = request.form.get("consignee_phone", "").strip()

        if party_details is None:
            party_details = ShipmentPartyDetails(
                quotation_id=quotation.id,
                enquiry_id=quotation.enquiry_id,
                created_by_id=current_user.id,
            )
            db.session.add(party_details)

        party_details.agent_name = agent_name
        party_details.agent_country = agent_country
        party_details.agent_contact_person = agent_contact_person
        party_details.agent_phone = agent_phone
        party_details.agent_email = agent_email
        party_details.agent_reference = agent_reference or None

        party_details.shipper_name = shipper_name
        party_details.shipper_address = shipper_address
        party_details.shipper_contact_person = shipper_contact_person
        party_details.shipper_phone = shipper_phone

        party_details.consignee_name = consignee_name
        party_details.consignee_address = consignee_address
        party_details.consignee_contact_person = consignee_contact_person
        party_details.consignee_phone = consignee_phone

        db.session.commit()
        flash("Agent, shipper and consignee details saved successfully.", "success")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    return render_template("quotations/party_details.html", quotation=quotation, party_details=party_details)

@quotations_bp.route("/<int:quotation_id>/approve", methods=["POST"])
@login_required
def approve_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    if quotation.status != "pending":
        flash(f"Quotation {quotation.quotation_number} is already {quotation.status}.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    quotation.status = "approved"
    quotation.approved_by_id = current_user.id
    quotation.approved_at = datetime.now()
    quotation.rejection_reason = None
    db.session.commit()

    flash(f"Quotation {quotation.quotation_number} approved successfully.", "success")
    return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

@quotations_bp.route("/<int:quotation_id>/reject", methods=["POST"])
@login_required
def reject_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    if quotation.status != "pending":
        flash(f"Quotation {quotation.quotation_number} is already {quotation.status}.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    rejection_reason = request.form.get("rejection_reason", "").strip()
    if not rejection_reason:
        flash("Rejection reason is required.", "danger")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    quotation.status = "rejected"
    quotation.rejection_reason = rejection_reason
    quotation.approved_by_id = None
    quotation.approved_at = None
    db.session.commit()

    flash(f"Quotation {quotation.quotation_number} rejected successfully.", "success")
    return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

@quotations_bp.route("/<int:quotation_id>/download")
@login_required
def download_quotation_pdf(quotation_id):
    quotation = get_quotation_or_404(quotation_id)

    logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
    logo_url = f"file:///{logo_path.replace('\\', '/')}"

    logo2_path = os.path.join(current_app.root_path, 'static', 'images', 'logo2.png')
    logo2_url = f"file:///{logo2_path.replace('\\', '/')}"

    html_content = render_template(
        "quotations/pdf_template.html",
        quotation=quotation,
        logo_url=logo_url,
        logo2_url=logo2_url
    )

    options = {
        'enable-local-file-access': None,
        'encoding': 'UTF-8'
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
    response.headers["Content-Disposition"] = f'attachment; filename=Quotation_{quotation.quotation_number}.pdf'

    return response

@quotations_bp.route("/<int:quotation_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    if quotation.status != "pending":
        flash("You can only edit pending quotations.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    if request.method == "POST":
        ocean_air_freight = Decimal(request.form.get("ocean_air_freight") or 0)
        origin_charges = Decimal(request.form.get("origin_charges") or 0)
        destination_charges = Decimal(request.form.get("destination_charges") or 0)
        insurance_charges = Decimal(request.form.get("insurance_charges") or 0)
        other_surcharges = Decimal(request.form.get("other_surcharges") or 0)
        
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
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

@quotations_bp.route("/<int:quotation_id>/delete", methods=["POST"])
@login_required
def delete_quotation(quotation_id):
    quotation = get_quotation_or_404(quotation_id)
    if quotation.status == "approved":
        flash("Approved quotations cannot be deleted.", "warning")
        return redirect(url_for("quotations.view_quotation", quotation_id=quotation.id))

    quotation.is_deleted = True
    db.session.commit()
    flash("Quotation deleted successfully.", "success")
    return redirect(url_for("quotations.quotation_list"))
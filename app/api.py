from datetime import datetime, timezone, date
from decimal import Decimal
from flask import Blueprint, request, jsonify, send_file, render_template, current_app, make_response
from flask_login import login_user, current_user
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from app import db
from app.models import (
    User, Client, Shipment, Enquiry, Quotation, 
    ClientStatusHistory, ShipmentMilestone, ShipmentDocument, 
    ShipmentCustomsClearance, ShipmentPartyDetails, ShipmentClosure
)
from app.sales_scope import scope_enquiries

# బ్లూప్రింట్ డిఫైన్ చేయడం (ఇదే మిస్ అయింది)
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request."
            }), 400

        email = data.get("username", "").strip().lower()
        password = data.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 401

        if not user.check_password(password):
            return jsonify({
                "success": False,
                "message": "Invalid password."
            }), 401

        if not user.is_active_user:
            return jsonify({
                "success": False,
                "message": "User is inactive."
            }), 401

        login_user(user)

        access_token = create_access_token(identity=str(user.id))

        return jsonify({
            "success": True,
            "message": "Login successful.",
            "access_token": access_token,
            "user": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "role": user.role,
            }
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@api_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    user_id = get_jwt_identity()

    return jsonify({
        "success": True,
        "user_id": user_id,
        "counts": {
            "clients": Client.query.count(),
            "shipments": Shipment.query.count(),
            "enquiries": Enquiry.query.count(),
            "quotations": Quotation.query.count(),
        }
    })


@api_bp.route("/clients", methods=["GET"])
@jwt_required()
def get_clients():
    try:
        clients = (
            Client.query
            .filter_by(is_archived=False)
            .order_by(Client.company_name.asc())
            .all()
        )

        data = []

        for client in clients:
            data.append({
                "id": client.id,
                "client_reference": client.client_reference,
                "company_name": client.company_name,
                "contact_person_name": client.contact_person_name,
                "primary_phone": client.primary_phone,
                "email": client.email,
                "status": client.status
            })

        return jsonify({
            "success": True,
            "count": len(data),
            "clients": data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@api_bp.route("/clients/add", methods=["POST"])
@jwt_required()
def api_add_client():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        user_id = get_jwt_identity()

        raw_tags = data.get("tags", "")
        if isinstance(raw_tags, str):
            tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags_list = raw_tags
        else:
            tags_list = []

        services = data.get("services_needed", [])
        if isinstance(services, str):
            services_list = [s.strip() for s in services.split(",") if s.strip()]
        elif isinstance(services, list):
            services_list = services
        else:
            services_list = []

        client = Client(
            company_name=data.get("company_name"),
            category=data.get("category"),
            status=data.get("status", "lead"),
            contact_person_name=data.get("contact_person_name"),
            designation=data.get("designation"),
            primary_phone=data.get("primary_phone"),
            secondary_phone=data.get("secondary_phone"),
            email=data.get("email"),
            website_url=data.get("website_url"),
            address_line_1=data.get("address_line_1"),
            address_line_2=data.get("address_line_2"),
            industry_sector=data.get("industry_sector"),
            services_needed=services_list,
            assigned_to_id=int(user_id) if user_id else None,
            lead_source=data.get("lead_source"),
            priority_level=data.get("priority_level", "medium"),
            notes=data.get("notes"),
            tags=tags_list,
            company_registration_number=data.get("company_registration_number"),
            tax_vat_number=data.get("tax_vat_number"),
            license_number=data.get("license_number"),
            payment_terms=data.get("payment_terms"),
            created_by_id=int(user_id) if user_id else None
        )

        db.session.add(client)
        db.session.flush()

        client.client_reference = f"CLT-{datetime.now(timezone.utc).year}-{client.id:06d}"
        
        db.session.add(ClientStatusHistory(
            client_id=client.id, 
            old_status=None, 
            new_status=client.status, 
            changed_by_id=int(user_id) if user_id else None, 
            remarks="Client created via Flutter API."
        ))

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Client created successfully!",
            "client_id": client.id
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Exception: {str(e)}"
        }), 500


@api_bp.route("/clients/edit/<int:client_id>", methods=["PUT"])
@jwt_required()
def api_edit_client(client_id):
    try:
        client = Client.query.get_or_404(client_id)
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        user_id = get_jwt_identity()

        raw_tags = data.get("tags", "")
        if isinstance(raw_tags, str):
            tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags_list = raw_tags
        else:
            tags_list = client.tags

        services = data.get("services_needed", [])
        if isinstance(services, str):
            services_list = [s.strip() for s in services.split(",") if s.strip()]
        elif isinstance(services, list):
            services_list = services
        else:
            services_list = client.services_needed

        new_status = data.get("status", client.status)
        if client.status != new_status:
            db.session.add(ClientStatusHistory(
                client_id=client.id, 
                old_status=client.status, 
                new_status=new_status, 
                changed_by_id=int(user_id) if user_id else None, 
                remarks="Status updated via Flutter API."
            ))

        client.company_name = data.get("company_name", client.company_name)
        client.category = data.get("category", client.category)
        client.status = new_status
        client.contact_person_name = data.get("contact_person_name", client.contact_person_name)
        client.designation = data.get("designation", client.designation)
        client.primary_phone = data.get("primary_phone", client.primary_phone)
        client.secondary_phone = data.get("secondary_phone", client.secondary_phone)
        client.email = data.get("email", client.email)
        client.website_url = data.get("website_url", client.website_url)
        client.address_line_1 = data.get("address_line_1", client.address_line_1)
        client.address_line_2 = data.get("address_line_2", client.address_line_2)
        client.industry_sector = data.get("industry_sector", client.industry_sector)
        client.services_needed = services_list
        client.lead_source = data.get("lead_source", client.lead_source)
        client.priority_level = data.get("priority_level", client.priority_level)
        client.notes = data.get("notes", client.notes)
        client.tags = tags_list
        client.company_registration_number = data.get("company_registration_number", client.company_registration_number)
        client.tax_vat_number = data.get("tax_vat_number", client.tax_vat_number)
        client.license_number = data.get("license_number", client.license_number)
        client.payment_terms = data.get("payment_terms", client.payment_terms)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Client updated successfully!"
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Exception: {str(e)}"
        }), 500


@api_bp.route("/change-password", methods=["POST"])
@jwt_required()
def api_change_password():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        if not user.check_password(current_password):
            return jsonify({
                "success": False,
                "message": "Incorrect current password."
            }), 400

        if not new_password or len(new_password) < 8:
            return jsonify({
                "success": False,
                "message": "New password must be at least 8 characters long."
            }), 400

        if new_password != confirm_password:
            return jsonify({
                "success": False,
                "message": "New passwords do not match."
            }), 400

        user.set_password(new_password)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Password changed successfully!"
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Exception: {str(e)}"
        }), 500


@api_bp.route("/enquiries", methods=["GET"])
@jwt_required()
def api_get_enquiries():
    try:
        enquiries = (
            db.session.execute(
                scope_enquiries(db.select(Enquiry))
                .order_by(Enquiry.created_at.desc())
            )
            .scalars()
            .all()
        )

        enquiry_list = []
        for e in enquiries:
            enquiry_list.append({
                "id": e.id,
                "enquiry_reference": e.enquiry_reference,
                "company_name": e.client.company_name if e.client else "N/A",
                "origin": e.origin,
                "destination": e.destination,
                "mode_of_shipment": e.mode_of_shipment,
                "status": e.status,
                "created_at": e.created_at.strftime("%d %b %Y") if e.created_at else ""
            })

        return jsonify({
            "success": True,
            "count": len(enquiry_list),
            "enquiries": enquiry_list
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/enquiries/<int:enquiry_id>", methods=["PUT"])
@jwt_required()
def api_update_enquiry(enquiry_id):
    try:
        enquiry = Enquiry.query.get_or_404(enquiry_id)
        data = request.get_json()

        enquiry.client_id = data.get("client_id", enquiry.client_id)
        enquiry.origin = data.get("origin", enquiry.origin)
        enquiry.destination = data.get("destination", enquiry.destination)
        enquiry.origin_port = data.get("origin_port", enquiry.origin_port)
        enquiry.destination_port = data.get("destination_port", enquiry.destination_port)
        enquiry.mode_of_shipment = data.get("mode_of_shipment", enquiry.mode_of_shipment)
        enquiry.cargo_description = data.get("cargo_description", enquiry.cargo_description)
        enquiry.cargo_weight_volume = data.get("cargo_weight_volume", enquiry.cargo_weight_volume)
        enquiry.handled_by_id = data.get("handled_by_id", enquiry.handled_by_id)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Enquiry updated successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@api_bp.route("/enquiries", methods=["POST"])
@jwt_required()
def api_add_enquiry():
    try:
        data = request.get_json()
        
        if not data.get("client_id") or not data.get("origin") or not data.get("destination") or not data.get("mode_of_shipment") or not data.get("cargo_description"):
            return jsonify({
                "success": False,
                "message": "Please fill all required fields"
            }), 400

        new_enquiry = Enquiry(
            client_id=data.get("client_id"),
            origin=data.get("origin"),
            destination=data.get("destination"),
            origin_port=data.get("origin_port"),
            destination_port=data.get("destination_port"),
            mode_of_shipment=data.get("mode_of_shipment"),
            cargo_description=data.get("cargo_description"),
            cargo_weight_volume=data.get("cargo_weight_volume"),
            incoterms=data.get("incoterms"),
            sales_coordinator_id=data.get("sales_coordinator_id"),
            additional_instructions=data.get("additional_instructions"),
            handled_by_id=data.get("handled_by_id"),
            status="open"
        )

        db.session.add(new_enquiry)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Enquiry created successfully"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/enquiries/<int:enquiry_id>", methods=["GET"])
@jwt_required()
def api_get_enquiry_detail(enquiry_id):
    try:
        enquiry = Enquiry.query.get_or_404(enquiry_id)
        
        return jsonify({
            "success": True,
            "enquiry": {
                "id": enquiry.id,
                "enquiry_reference": enquiry.enquiry_reference,
                "client_id": enquiry.client_id,
                "company_name": enquiry.client.company_name if enquiry.client else "N/A",
                "origin": enquiry.origin,
                "destination": enquiry.destination,
                "origin_port": enquiry.origin_port,
                "destination_port": enquiry.destination_port,
                "mode_of_shipment": enquiry.mode_of_shipment,
                "cargo_description": enquiry.cargo_description,
                "cargo_weight_volume": enquiry.cargo_weight_volume,
                "incoterms": enquiry.incoterms,
                "additional_instructions": enquiry.additional_instructions,
                "status": enquiry.status,
                "created_at": enquiry.created_at.strftime("%d %b %Y %H:%M") if enquiry.created_at else ""
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/enquiries/<int:enquiry_id>/pdf", methods=["GET"])
@jwt_required()
def api_download_enquiry_pdf(enquiry_id):
    try:
        enquiry = Enquiry.query.get_or_404(enquiry_id)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()

        title_style = styles["Heading1"]
        title_style.alignment = TA_CENTER

        elements = []

        elements.append(Paragraph("<b>ABC FREIGHT LOGISTICS LLC</b>", title_style))
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"ENQUIRY REPORT: {enquiry.enquiry_reference}", title_style))
        elements.append(Spacer(1, 15))

        data = [
            ["Enquiry Reference", str(enquiry.enquiry_reference or "N/A")],
            ["Client Company", str(enquiry.client.company_name if enquiry.client else "N/A")],
            ["Origin", str(enquiry.origin or "N/A")],
            ["Destination", str(enquiry.destination or "N/A")],
            ["Mode of Shipment", str(enquiry.mode_of_shipment or "N/A")],
            ["Cargo Description", str(enquiry.cargo_description or "N/A")],
            ["Status", str(enquiry.status or "N/A")],
        ]

        table = Table(data, colWidths=[180, 360])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#7f1d1d")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f9fafb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Enquiry_{enquiry.enquiry_reference}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

def generate_quotation_number():
    current_year = datetime.now().year
    prefix = f"QUO-{current_year}-"
    last_quotation = db.session.execute(
        db.select(Quotation).where(Quotation.quotation_number.like(f"{prefix}%")).order_by(Quotation.id.desc())
    ).scalars().first()
    
    next_number = int(last_quotation.quotation_number.split("-")[-1]) + 1 if last_quotation else 1
    return f"{prefix}{next_number:06d}"

@api_bp.route("/enquiries/<int:enquiry_id>/quotations/add", methods=["POST"])
@jwt_required()
def api_add_quotation(enquiry_id):
    try:
        enquiry = Enquiry.query.get_or_404(enquiry_id)
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        ocean_air_freight = Decimal(str(data.get("ocean_air_freight") or 0))
        origin_charges = Decimal(str(data.get("origin_charges") or 0))
        destination_charges = Decimal(str(data.get("destination_charges") or 0))
        insurance_charges = Decimal(str(data.get("insurance_charges") or 0))
        other_surcharges = Decimal(str(data.get("other_surcharges") or 0))
        
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges

        currency = data.get("currency")
        validity_date_str = data.get("validity_date")

        if not currency or not validity_date_str:
            return jsonify({
                "success": False,
                "message": "Currency and Validity Date are required."
            }), 400

        try:
            validity_date = datetime.strptime(validity_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid validity date format. Use YYYY-MM-DD."
            }), 400

        def parse_datetime(val):
            if not val or not str(val).strip():
                return None
            val_str = str(val).strip().replace('T', ' ')
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val_str, fmt)
                except ValueError:
                    continue
            return None

        etd = parse_datetime(data.get("etd"))
        cutoff_doc = parse_datetime(data.get("cutoff_date_documentation"))
        cutoff_cargo = parse_datetime(data.get("cutoff_date_cargo"))

        def parse_int(val):
            try:
                return int(val) if val is not None and str(val).strip() != "" else None
            except (ValueError, TypeError):
                return None

        no_of_containers = parse_int(data.get("no_of_containers"))
        free_time_days = parse_int(data.get("free_time_days"))
        transit_time_days = parse_int(data.get("transit_time_days"))

        new_quotation = Quotation(
            quotation_number=generate_quotation_number(),
            enquiry_id=enquiry.id,
            quotation_amount=total_amount,
            currency=currency,
            validity_date=validity_date,
            origin=enquiry.origin,
            destination=enquiry.destination,
            origin_port=enquiry.origin_port,
            destination_port=enquiry.destination_port,
            mode_of_shipment=enquiry.mode_of_shipment,
            cargo_description=enquiry.cargo_description,
            cargo_weight_volume=enquiry.cargo_weight_volume,
            incoterms=data.get("incoterms") or enquiry.incoterms,
            shipping_line_airline=data.get("shipping_line_airline"),
            no_of_containers=no_of_containers,
            container_type_quota=data.get("container_type_quota"),
            etd=etd,
            cutoff_date_documentation=cutoff_doc,
            cutoff_date_cargo=cutoff_cargo,
            free_time_days=free_time_days,
            transit_time_days=transit_time_days,
            hs_code=data.get("hs_code"),
            payment_terms=data.get("payment_terms"),
            remarks_terms=data.get("remarks_terms"),
            ocean_air_freight=ocean_air_freight,
            origin_charges=origin_charges,
            destination_charges=destination_charges,
            insurance_charges=insurance_charges,
            other_surcharges=other_surcharges,
            status="pending",
            created_by_id=int(get_jwt_identity())
        )

        enquiry.status = "quoted"
        
        db.session.add(new_quotation)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Quotation created successfully!"
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Error: {str(e)}"
        }), 500

@api_bp.route("/quotations/<int:quotation_id>", methods=["GET"])
@jwt_required()
def api_view_quotation(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        
        created_by_name = quotation.created_by.full_name if quotation.created_by else "System"
        approved_by_name = quotation.approved_by.full_name if quotation.approved_by else None

        client_name = "N/A"
        contact_person = "N/A"
        email = "N/A"
        phone = "N/A"

        if quotation.client:
            client_name = quotation.client.company_name
            contact_person = quotation.client.contact_person_name
            email = quotation.client.email
            phone = quotation.client.primary_phone
        elif quotation.enquiry and quotation.enquiry.client:
            client_name = quotation.enquiry.client.company_name
            contact_person = quotation.enquiry.client.contact_person_name
            email = quotation.enquiry.client.email
            phone = quotation.enquiry.client.primary_phone
        elif quotation.other_client_name:
            client_name = quotation.other_client_name

        return jsonify({
            "success": True,
            "quotation": {
                "id": quotation.id,
                "quotation_number": quotation.quotation_number,
                "status": quotation.status,
                "currency": quotation.currency or "USD",
                "validity_date": quotation.validity_date.strftime("%Y-%m-%d") if quotation.validity_date else None,
                "enquiry_reference": quotation.enquiry.enquiry_reference if quotation.enquiry else None,
                "enquiry_id": quotation.enquiry_id,
                "client_name": client_name,
                "contact_person": contact_person,
                "email": email,
                "phone": phone,
                "origin": quotation.origin,
                "destination": quotation.destination,
                "origin_port": quotation.origin_port,
                "destination_port": quotation.destination_port,
                "mode_of_shipment": quotation.mode_of_shipment,
                "cargo_description": quotation.cargo_description,
                "cargo_weight_volume": quotation.cargo_weight_volume,
                "shipping_line_airline": quotation.shipping_line_airline,
                "no_of_containers": quotation.no_of_containers,
                "container_type_quota": quotation.container_type_quota,
                "etd": quotation.etd.strftime("%Y-%m-%d %H:%M") if quotation.etd else None,
                "cutoff_date_documentation": quotation.cutoff_date_documentation.strftime("%Y-%m-%d %H:%M") if quotation.cutoff_date_documentation else None,
                "cutoff_date_cargo": quotation.cutoff_date_cargo.strftime("%Y-%m-%d %H:%M") if quotation.cutoff_date_cargo else None,
                "free_time_days": quotation.free_time_days,
                "transit_time_days": quotation.transit_time_days,
                "incoterms": quotation.incoterms,
                "hs_code": quotation.hs_code,
                "ocean_air_freight": float(quotation.ocean_air_freight or 0),
                "origin_charges": float(quotation.origin_charges or 0),
                "destination_charges": float(quotation.destination_charges or 0),
                "insurance_charges": float(quotation.insurance_charges or 0),
                "other_surcharges": float(quotation.other_surcharges or 0),
                "quotation_amount": float(quotation.quotation_amount or 0),
                "payment_terms": quotation.payment_terms,
                "remarks_terms": quotation.remarks_terms,
                "created_by": created_by_name,
                "created_at": quotation.created_at.strftime("%Y-%m-%d %H:%M") if quotation.created_at else None,
                "updated_at": quotation.updated_at.strftime("%Y-%m-%d %H:%M") if quotation.updated_at else None,
                "approved_by": approved_by_name,
                "approved_at": quotation.approved_at.strftime("%Y-%m-%d %H:%M") if quotation.approved_at else None,
                "rejection_reason": quotation.rejection_reason,
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server Error: {str(e)}"
        }), 500

@api_bp.route("/quotations", methods=["GET"])
@jwt_required()
def api_quotation_list():
    try:
        quotations = db.session.execute(
            db.select(Quotation).where(Quotation.is_deleted == False)
            .order_by(Quotation.created_at.desc())
        ).scalars().all()

        quotation_list = []
        for q in quotations:
            client_name = "N/A"
            if q.enquiry and q.enquiry.client:
                client_name = q.enquiry.client.company_name
            elif q.other_client_name:
                client_name = q.other_client_name
            elif q.client:
                client_name = q.client.company_name

            quotation_list.append({
                "id": q.id,
                "quotation_number": q.quotation_number,
                "status": q.status,
                "currency": q.currency or "USD",
                "quotation_amount": float(q.quotation_amount or 0),
                "validity_date": q.validity_date.strftime("%d %b %Y") if q.validity_date else "N/A",
                "created_at": q.created_at.strftime("%d %b %Y") if q.created_at else "N/A",
                "enquiry_reference": q.enquiry.enquiry_reference if q.enquiry else "Direct Quotation",
                "client_name": client_name
            })

        return jsonify({
            "success": True,
            "quotations": quotation_list
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Error: {str(e)}"
        }), 500

@api_bp.route("/quotations/<int:quotation_id>/edit", methods=["PUT"])
@jwt_required()
def api_edit_quotation(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        if quotation.status != "pending":
            return jsonify({
                "success": False,
                "message": "You can only edit pending quotations."
            }), 400

        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        ocean_air_freight = Decimal(str(data.get("ocean_air_freight") or 0))
        origin_charges = Decimal(str(data.get("origin_charges") or 0))
        destination_charges = Decimal(str(data.get("destination_charges") or 0))
        insurance_charges = Decimal(str(data.get("insurance_charges") or 0))
        other_surcharges = Decimal(str(data.get("other_surcharges") or 0))
        
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
        quotation.quotation_amount = total_amount
        quotation.ocean_air_freight = ocean_air_freight
        quotation.origin_charges = origin_charges
        quotation.destination_charges = destination_charges
        quotation.insurance_charges = insurance_charges
        quotation.other_surcharges = other_surcharges
        quotation.payment_terms = data.get("payment_terms", quotation.payment_terms)
        quotation.remarks_terms = data.get("remarks_terms", quotation.remarks_terms)
        
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Quotation updated successfully!"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Server Error: {str(e)}"
        }), 500

@api_bp.route("/quotations/<int:quotation_id>/party-details", methods=["GET", "POST"])
@jwt_required()
def api_manage_party_details(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)

        if quotation.status != "approved":
            return jsonify({
                "success": False,
                "message": "Agent, shipper and consignee details can be added only after quotation approval."
            }), 400

        party_details = db.session.execute(
            db.select(ShipmentPartyDetails).where(ShipmentPartyDetails.quotation_id == quotation.id)
        ).scalars().first()

        if request.method == "GET":
            return jsonify({
                "success": True,
                "quotation_number": quotation.quotation_number,
                "status": quotation.status,
                "party_details": {
                    "agent_name": party_details.agent_name if party_details else "",
                    "agent_country": party_details.agent_country if party_details else "",
                    "agent_contact_person": party_details.agent_contact_person if party_details else "",
                    "agent_phone": party_details.agent_phone if party_details else "",
                    "agent_email": party_details.agent_email if party_details else "",
                    "agent_reference": party_details.agent_reference if party_details else "",
                    "shipper_name": party_details.shipper_name if party_details else "",
                    "shipper_address": party_details.shipper_address if party_details else "",
                    "shipper_contact_person": party_details.shipper_contact_person if party_details else "",
                    "shipper_phone": party_details.shipper_phone if party_details else "",
                    "consignee_name": party_details.consignee_name if party_details else "",
                    "consignee_address": party_details.consignee_address if party_details else "",
                    "consignee_contact_person": party_details.consignee_contact_person if party_details else "",
                    "consignee_phone": party_details.consignee_phone if party_details else "",
                } if party_details else None
            }), 200

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request data."}), 400

        if party_details is None:
            party_details = ShipmentPartyDetails(
                quotation_id=quotation.id,
                enquiry_id=quotation.enquiry_id,
                created_by_id=int(get_jwt_identity()),
            )
            db.session.add(party_details)

        party_details.agent_name = str(data.get("agent_name") or "").strip()
        party_details.agent_country = str(data.get("agent_country") or "").strip()
        party_details.agent_contact_person = str(data.get("agent_contact_person") or "").strip()
        party_details.agent_phone = str(data.get("agent_phone") or "").strip()
        party_details.agent_email = str(data.get("agent_email") or "").strip()
        party_details.agent_reference = str(data.get("agent_reference") or "").strip() or None

        party_details.shipper_name = str(data.get("shipper_name") or "").strip()
        party_details.shipper_address = str(data.get("shipper_address") or "").strip()
        party_details.shipper_contact_person = str(data.get("shipper_contact_person") or "").strip()
        party_details.shipper_phone = str(data.get("shipper_phone") or "").strip()

        party_details.consignee_name = str(data.get("consignee_name") or "").strip()
        party_details.consignee_address = str(data.get("consignee_address") or "").strip()
        party_details.consignee_contact_person = str(data.get("consignee_contact_person") or "").strip()
        party_details.consignee_phone = str(data.get("consignee_phone") or "").strip()

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Agent, shipper and consignee details saved successfully."
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

def generate_shipment_reference():
    current_year = datetime.now().year
    prefix = f"SHP-{current_year}-"
    last_shipment = db.session.execute(
        db.select(Shipment).where(Shipment.shipment_reference.like(f"{prefix}%")).order_by(Shipment.id.desc())
    ).scalars().first()
    
    next_number = int(last_shipment.shipment_reference.split("-")[-1]) + 1 if last_shipment else 1
    return f"{prefix}{next_number:06d}"

@api_bp.route("/quotations/<int:quotation_id>/convert-to-shipment", methods=["POST"])
@jwt_required()
def api_convert_to_shipment(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        
        if quotation.status != "approved":
            return jsonify({
                "success": False,
                "message": "Only approved quotations can be converted to shipments."
            }), 400

        party_details = db.session.execute(
            db.select(ShipmentPartyDetails).where(ShipmentPartyDetails.quotation_id == quotation.id)
        ).scalars().first()

        if not party_details:
            return jsonify({
                "success": False,
                "message": "Please fill in Agent, Shipper, and Consignee details before converting to shipment."
            }), 400

        existing_shipment = db.session.execute(
            db.select(Shipment).where(Shipment.quotation_id == quotation.id)
        ).scalars().first()

        if existing_shipment:
            return jsonify({
                "success": False,
                "message": "A shipment has already been created from this quotation."
            }), 400

        user_id = int(get_jwt_identity())

        new_shipment = Shipment(
            shipment_reference=generate_shipment_reference(), 
            quotation_id=quotation.id,
            enquiry_id=quotation.enquiry_id,
            client_id=quotation.client_id,
            other_client_name=quotation.other_client_name,
            origin=quotation.origin,
            destination=quotation.destination,
            mode_of_shipment=quotation.mode_of_shipment,
            cargo_description=quotation.cargo_description,
            cargo_weight_volume=quotation.cargo_weight_volume,
            container_type=quotation.container_type_quota,
            shipping_line=quotation.shipping_line_airline,
            shipment_status="active",
            current_stage="booked",
            status="booked",
            handled_by_id=user_id,
            created_by_id=user_id
        )

        db.session.add(new_shipment)
        quotation.status = "converted"
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Quotation successfully converted to shipment!",
            "shipment_id": new_shipment.id
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Server Error: {str(e)}"
        }), 500

@api_bp.route("/quotations/direct/add", methods=["POST"])
@jwt_required()
def api_add_direct_quotation():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request data."}), 400

        client_type = data.get("client_type", "existing")
        client_id = data.get("client_id")
        other_client_name = data.get("other_client_name")

        if client_type == "existing" and not client_id:
            return jsonify({"success": False, "message": "Please select an existing client."}), 400
        if client_type == "new" and not other_client_name:
            return jsonify({"success": False, "message": "Please enter new client name."}), 400

        ocean_air_freight = Decimal(str(data.get("ocean_air_freight") or 0))
        origin_charges = Decimal(str(data.get("origin_charges") or 0))
        destination_charges = Decimal(str(data.get("destination_charges") or 0))
        insurance_charges = Decimal(str(data.get("insurance_charges") or 0))
        other_surcharges = Decimal(str(data.get("other_surcharges") or 0))
        
        total_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        
        validity_date_str = data.get("validity_date")
        if not validity_date_str:
            return jsonify({"success": False, "message": "Validity Date is required."}), 400

        try:
            validity_date = datetime.strptime(validity_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format. Use YYYY-MM-DD."}), 400

        def parse_datetime(val):
            if not val or not str(val).strip():
                return None
            val_str = str(val).strip().replace('T', ' ')
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val_str, fmt)
                except ValueError:
                    continue
            return None

        quotation = Quotation(
            quotation_number=generate_quotation_number(),
            enquiry_id=None,
            client_id=int(client_id) if client_type == "existing" and client_id else None,
            other_client_name=other_client_name if client_type == "new" else None,
            quotation_amount=total_amount,
            currency=data.get("currency", "USD"),
            validity_date=validity_date,
            origin=data.get("origin"),
            destination=data.get("destination"),
            origin_port=data.get("origin_port"),
            destination_port=data.get("destination_port"),
            mode_of_shipment=data.get("mode_of_shipment"),
            cargo_description=data.get("cargo_description"),
            cargo_weight_volume=data.get("cargo_weight_volume"),
            shipping_line_airline=data.get("shipping_line_airline"),
            no_of_containers=int(data.get("no_of_containers")) if data.get("no_of_containers") else None,
            container_type_quota=data.get("container_type_quota"),
            etd=parse_datetime(data.get("etd")),
            cutoff_date_documentation=parse_datetime(data.get("cutoff_date_documentation")),
            cutoff_date_cargo=parse_datetime(data.get("cutoff_date_cargo")),
            free_time_days=int(data.get("free_time_days")) if data.get("free_time_days") else None,
            transit_time_days=int(data.get("transit_time_days")) if data.get("transit_time_days") else None,
            incoterms=data.get("incoterms"),
            hs_code=data.get("hs_code"),
            payment_terms=data.get("payment_terms"),
            remarks_terms=data.get("remarks_terms"),
            ocean_air_freight=ocean_air_freight,
            origin_charges=origin_charges,
            destination_charges=destination_charges,
            insurance_charges=insurance_charges,
            other_surcharges=other_surcharges,
            status="pending",
            created_by_id=int(get_jwt_identity())
        )

        db.session.add(quotation)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Direct quotation created successfully.",
            "quotation_id": quotation.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route("/quotations/<int:quotation_id>/approve", methods=["POST"])
@jwt_required()
def api_approve_quotation(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        quotation.status = "approved"
        db.session.commit()
        return jsonify({"success": True, "message": "Quotation approved successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route("/quotations/<int:quotation_id>/reject", methods=["POST"])
@jwt_required()
def api_reject_quotation(quotation_id):
    try:
        data = request.get_json()
        quotation = Quotation.query.get_or_404(quotation_id)
        quotation.status = "rejected"
        quotation.rejection_reason = data.get("rejection_reason", "No reason provided")
        db.session.commit()
        return jsonify({"success": True, "message": "Quotation rejected successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route("/quotations/<int:quotation_id>/delete", methods=["POST"])
@jwt_required()
def api_delete_quotation(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        quotation.is_deleted = True
        db.session.commit()
        return jsonify({"success": True, "message": "Quotation deleted successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route("/quotations/<int:quotation_id>/pdf", methods=["GET"])
def api_download_quotation_pdf(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)

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

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

def can_view_shipment(shipment):
    return True

@api_bp.route("/shipments", methods=["GET"])
@jwt_required()
def api_get_shipments():
    try:
        shipments = db.session.execute(db.select(Shipment).order_by(Shipment.created_at.desc())).scalars().all()
        
        shipments_list = []
        for s in shipments:
            client_name = "N/A"
            if s.client:
                client_name = s.client.company_name
            elif s.other_client_name:
                client_name = s.other_client_name
                
            shipments_list.append({
                "id": s.id,
                "shipment_reference": s.shipment_reference,
                "hbl_no": s.hbl_no,
                "shipment_status": s.shipment_status,
                "mode_of_shipment": s.mode_of_shipment,
                "origin": s.origin,
                "destination": s.destination,
                "client_name": client_name
            })
            
        return jsonify({"success": True, "shipments": shipments_list}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route("/shipments/<int:shipment_id>", methods=["GET"], endpoint="unique_shipment_detail_api")
@jwt_required()
def api_get_shipment_detail(shipment_id):
    try:
        shipment = db.get_or_404(Shipment, shipment_id)
        
        client_name = "N/A"
        if shipment.client:
            client_name = shipment.client.company_name
        elif shipment.other_client_name:
            client_name = shipment.other_client_name

        # 1. మైలురాళ్లు
        milestones = db.session.execute(
            db.select(ShipmentMilestone)
            .where(ShipmentMilestone.shipment_id == shipment.id)
            .order_by(ShipmentMilestone.completed_at.asc())
        ).scalars().all()

        milestones_list = [{
            "stage": m.stage,
            "completed_by": m.completed_by.full_name if m.completed_by else "N/A",
            "completed_at": m.completed_at.strftime("%d %b %Y %H:%M") if m.completed_at else ""
        } for m in milestones]

        # 2. డాక్యుమెంట్లు
        documents = db.session.execute(
            db.select(ShipmentDocument)
            .where(ShipmentDocument.shipment_id == shipment.id)
            .order_by(ShipmentDocument.id.asc())
        ).scalars().all()

        docs_list = [{
            "id": d.id,
            "document_name": d.document_name,
            "document_type": d.document_type,
            "status": d.status,
            "file_path": d.file_path,
            "original_filename": d.original_filename,
            "remarks": d.remarks
        } for d in documents]

        # 3. కస్టమ్స్ క్లియరెన్స్
        customs = db.session.execute(
            db.select(ShipmentCustomsClearance)
            .where(ShipmentCustomsClearance.shipment_id == shipment.id)
        ).scalars().first()

        customs_data = None
        if customs:
            customs_data = {
                "clearance_required": customs.clearance_required,
                "clearance_status": customs.clearance_status,
                "clearing_agent_name": customs.clearing_agent_name,
                "clearance_date": customs.clearance_date.strftime("%Y-%m-%d") if customs.clearance_date else None,
                "remarks": customs.remarks
            }

        # 4. క్లోజింగ్ డేటా (ఇది మిస్ అయింది)
        closure = db.session.execute(
            db.select(ShipmentClosure)
            .where(ShipmentClosure.shipment_id == shipment.id)
        ).scalars().first()

        closure_data = None
        if closure:
            closure_data = {
                "closing_status": closure.closing_status,
                "closing_date": closure.closing_date.strftime("%d %b %Y %H:%M") if closure.closing_date else None,
                "closing_notes": closure.closing_notes,
                "client_feedback": closure.client_feedback,
                "client_rating": closure.client_rating,
                "document_archive_confirmed": closure.document_archive_confirmed
            }

        shipment_data = {
            "id": shipment.id,
            "shipment_reference": shipment.shipment_reference,
            "hbl_no": shipment.hbl_no,
            "shipment_status": shipment.shipment_status,
            "mode_of_shipment": shipment.mode_of_shipment,
            "client_name": client_name,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "shipping_line": shipment.shipping_line,
            "vessel": shipment.vessel,
            "container_no": shipment.container_no,
            "container_type": shipment.container_type,
            "cargo_description": shipment.cargo_description,
            "cargo_weight_volume": shipment.cargo_weight_volume,
            "volume": getattr(shipment, "volume", None),
            "etd": shipment.etd.strftime("%d %b %Y %H:%M") if shipment.etd else None,
            "eta": shipment.eta.strftime("%d %b %Y %H:%M") if shipment.eta else None,
            "milestones": milestones_list,
            "documents": docs_list,
            "customs_clearance": customs_data,
            "shipment_closure": closure_data  # యాప్‌కి పంపుతున్నాము
        }

        return jsonify({
            "success": True,
            "shipment": shipment_data
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/shipments/create-direct", methods=["POST"])
@jwt_required()
def api_create_direct_shipment():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request data."}), 400
        
        client_type = str(data.get("client_type") or "existing").strip()
        client_id = data.get("client_id")
        other_client_name = str(data.get("other_client_name") or "").strip()
        
        origin = str(data.get("origin") or "").strip()
        origin_port = str(data.get("origin_port") or "").strip()
        destination = str(data.get("destination") or "").strip()
        destination_port = str(data.get("destination_port") or "").strip()
        mode_of_shipment = str(data.get("mode_of_shipment") or "").strip()
        
        hbl_no = str(data.get("hbl_no") or "").strip()
        shipping_line = str(data.get("shipping_line") or "").strip()
        vessel = str(data.get("vessel") or "").strip()
        
        cargo_description = str(data.get("cargo_description") or "").strip()
        cargo_weight_volume = str(data.get("cargo_weight_volume") or "").strip()
        
        raw_containers = data.get("no_of_containers")
        no_of_containers = int(raw_containers) if raw_containers and str(raw_containers).strip() else None
        
        container_type = str(data.get("container_type") or "40HC").strip()
        container_no = str(data.get("container_no") or "").strip()
        
        try:
            ocean_air_freight = Decimal(str(data.get("ocean_air_freight") or "0.00").strip() or "0.00")
            origin_charges = Decimal(str(data.get("origin_charges") or "0.00").strip() or "0.00")
            destination_charges = Decimal(str(data.get("destination_charges") or "0.00").strip() or "0.00")
            insurance_charges = Decimal(str(data.get("insurance_charges") or "0.00").strip() or "0.00")
            other_surcharges = Decimal(str(data.get("other_surcharges") or "0.00").strip() or "0.00")
        except Exception:
            return jsonify({"success": False, "message": "Invalid cost format. Please check the amounts."}), 400
            
        quotation_amount = ocean_air_freight + origin_charges + destination_charges + insurance_charges + other_surcharges
        currency = str(data.get("currency") or "USD").strip()

        if not origin or not destination or not cargo_description:
            return jsonify({"success": False, "message": "Origin, Destination, and Cargo Description are required."}), 400

        user_id = int(get_jwt_identity())

        direct_quotation = Quotation(
            quotation_number=f"DIR-QUO-{int(datetime.now().timestamp())}",
            client_id=int(client_id) if client_type == "existing" and client_id else None,
            other_client_name=other_client_name if client_type == "new" else None,
            quotation_amount=quotation_amount,
            currency=currency,
            validity_date=date.today(),
            status="approved",
            origin=origin,
            destination=destination,
            mode_of_shipment=mode_of_shipment,
            cargo_description=cargo_description,
            cargo_weight_volume=cargo_weight_volume,
            created_by_id=user_id
        )
        db.session.add(direct_quotation)
        db.session.flush()

        shipment = Shipment(
            shipment_reference=generate_shipment_reference(),
            quotation_id=direct_quotation.id,
            client_id=int(client_id) if client_type == "existing" and client_id else None,
            other_client_name=other_client_name if client_type == "new" else None,
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
            handled_by_id=user_id,
            created_by_id=user_id,
        )
        db.session.add(shipment)
        db.session.flush()

        # 1. డిఫాల్ట్ 'booked' మైలురాయిని (Milestone) ఆటోమేటిక్‌గా యాడ్ చేస్తున్నాం
        initial_milestone = ShipmentMilestone(
            shipment_id=shipment.id,
            stage="booked",
            completed_by_id=user_id,
        )
        db.session.add(initial_milestone)

        # 2. డిఫాల్ట్ డాక్యుమెంట్లు యాడ్ చేయడం
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
            shipment_document = ShipmentDocument(
                shipment_id=shipment.id,
                document_type=document_type,
                document_name=document_name,
                status="pending",
                created_by_id=user_id,
            )
            db.session.add(shipment_document)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Direct Shipment {shipment.shipment_reference} created successfully.",
            "shipment_id": shipment.id
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@api_bp.route("/shipments/track", methods=["GET"])
@jwt_required()
def api_track_shipment():
    try:
        search_query = request.args.get("tracking_number", "").strip()
        mode_filter = request.args.get("mode", "").strip()

        if not search_query:
            return jsonify({
                "success": False,
                "message": "Tracking number or reference is required."
            }), 400

        shipment = db.session.execute(
            db.select(Shipment)
            .where(
                (Shipment.shipment_reference == search_query) | 
                (Shipment.hbl_no == search_query)
            )
        ).scalars().first()

        if not shipment:
            return jsonify({
                "success": False,
                "message": "No records match the provided HBL/Reference number."
            }), 404

        if mode_filter and shipment.mode_of_shipment != mode_filter:
            return jsonify({
                "success": False,
                "message": "The shipment does not match the selected transport mode."
            }), 400

        if not can_view_shipment(shipment):
            return jsonify({
                "success": False,
                "message": "You do not have permission to track this shipment."
            }), 403

        documents = db.session.execute(
            db.select(ShipmentDocument)
            .where(ShipmentDocument.shipment_id == shipment.id)
            .order_by(ShipmentDocument.document_name)
        ).scalars().all()

        docs_list = [{
            "id": d.id,
            "document_name": d.document_name,
            "document_type": d.document_type,
            "status": d.status
        } for d in documents]

        milestones = db.session.execute(
            db.select(ShipmentMilestone)
            .where(ShipmentMilestone.shipment_id == shipment.id)
            .order_by(ShipmentMilestone.completed_at)
        ).scalars().all()

        milestones_list = [{
            "stage": m.stage,
            "completed_at": m.completed_at.strftime("%d %b %Y, %H:%M") if m.completed_at else ""
        } for m in milestones]

        client_name = "N/A"
        if shipment.client:
            client_name = shipment.client.company_name
        elif shipment.other_client_name:
            client_name = shipment.other_client_name

        shipment_data = {
            "id": shipment.id,
            "shipment_reference": shipment.shipment_reference,
            "hbl_no": shipment.hbl_no,
            "shipment_status": shipment.shipment_status,
            "mode_of_shipment": shipment.mode_of_shipment,
            "current_stage": shipment.current_stage,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "client_name": client_name,
            "shipping_line": shipment.shipping_line,
            "vessel": shipment.vessel,
            "container_no": shipment.container_no,
            "container_type": shipment.container_type,
            "cargo_description": shipment.cargo_description,
            "volume": shipment.volume or shipment.cargo_weight_volume,
            "etd": shipment.etd.strftime("%d %b %Y") if shipment.etd else None,
            "eta": shipment.eta.strftime("%d %b %Y") if shipment.eta else None,
        }

        return jsonify({
            "success": True,
            "shipment": shipment_data,
            "shipment_stages": SHIPMENT_STAGES,
            "milestones": milestones_list,
            "documents": docs_list
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# ==========================================
# COMPLETE SHIPMENT STAGE (API ROUTE)
# ==========================================
@api_bp.route("/shipments/<int:shipment_id>/stage/<stage>", methods=["POST"])
@jwt_required()
def api_complete_shipment_stage(shipment_id, stage):
    try:
        shipment = Shipment.query.get_or_404(shipment_id)
        user_id = int(get_jwt_identity())

        # Check if stage already completed
        existing = ShipmentMilestone.query.filter_by(shipment_id=shipment.id, stage=stage).first()
        if existing:
            return jsonify({"success": False, "message": "This shipment stage is already completed."}), 400

        milestone = ShipmentMilestone(
            shipment_id=shipment.id,
            stage=stage,
            completed_by_id=user_id
        )
        db.session.add(milestone)
        
        shipment.current_stage = stage
        if stage == "delivered":
            shipment.shipment_status = "delivered"
        elif stage == "in_transit":
            shipment.shipment_status = "in_transit"
        elif stage == "closed_completed":
            shipment.shipment_status = "closed"

        db.session.commit()
        return jsonify({"success": True, "message": f"Stage {stage} completed successfully."}), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# UPDATE CUSTOMS CLEARANCE (API ROUTE)
# ==========================================
@api_bp.route("/shipments/<int:shipment_id>/customs-clearance", methods=["POST"])
@jwt_required()
def api_update_shipment_customs(shipment_id):
    try:
        shipment = Shipment.query.get_or_404(shipment_id)
        user_id = int(get_jwt_identity())
        
        data = request.get_json(silent=True) or request.form
        
        clearance_required_val = str(data.get("clearance_required") or "").strip().lower()
        clearance_required = clearance_required_val in ["yes", "true", "1"]

        clearance_status = str(data.get("clearance_status") or "pending").strip().lower()
        clearing_agent_name = str(data.get("clearing_agent_name") or "").strip()
        clearance_date_str = str(data.get("clearance_date") or "").strip()
        remarks = str(data.get("customs_remarks") or data.get("remarks") or "").strip()

        clearance_date = None
        if clearance_date_str:
            try:
                clearance_date = datetime.strptime(clearance_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        customs = ShipmentCustomsClearance.query.filter_by(shipment_id=shipment.id).first()
        if not customs:
            customs = ShipmentCustomsClearance(shipment_id=shipment.id, created_by_id=user_id)
            db.session.add(customs)

        customs.clearance_required = clearance_required
        customs.clearance_status = clearance_status if clearance_required else "not_required"
        customs.clearing_agent_name = clearing_agent_name or None
        customs.clearance_date = clearance_date if clearance_required else None
        customs.remarks = remarks or None
        customs.updated_by_id = user_id

        db.session.commit()
        return jsonify({"success": True, "message": "Customs clearance updated successfully."}), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# CLOSE SHIPMENT (API ROUTE)
# ==========================================
@api_bp.route("/shipments/<int:shipment_id>/close", methods=["POST"])
@jwt_required()
def api_close_shipment_record(shipment_id):
    try:
        shipment = Shipment.query.get_or_404(shipment_id)
        user_id = int(get_jwt_identity())
        
        data = request.get_json(silent=True) or request.form
        closing_status = str(data.get("closing_status") or "delivered").strip().lower()
        closing_notes = str(data.get("closing_notes") or "").strip()
        client_feedback = str(data.get("client_feedback") or "").strip()
        client_rating_str = str(data.get("client_rating") or "").strip()
        archive_confirmed = str(data.get("document_archive_confirmed") or "").strip().lower()

        if archive_confirmed not in ["yes", "true", "1", "on"]:
            return jsonify({"success": False, "message": "Document Archive Confirmation is required."}), 400

        client_rating = int(client_rating_str) if client_rating_str.isdigit() else None

        existing_closure = ShipmentClosure.query.filter_by(shipment_id=shipment.id).first()
        if not existing_closure:
            closure = ShipmentClosure(
                shipment_id=shipment.id,
                closing_status=closing_status,
                closing_date=datetime.now(),
                closing_notes=closing_notes or None,
                document_archive_confirmed=True,
                client_feedback=client_feedback or None,
                client_rating=client_rating,
                closed_by_id=user_id,
                updated_by_id=user_id
            )
            db.session.add(closure)
        else:
            existing_closure.closing_status = closing_status
            existing_closure.closing_notes = closing_notes or None
            existing_closure.document_archive_confirmed = True
            existing_closure.client_feedback = client_feedback or None
            existing_closure.client_rating = client_rating
            existing_closure.updated_by_id = user_id

        closed_milestone = ShipmentMilestone.query.filter_by(shipment_id=shipment.id, stage="closed_completed").first()
        if not closed_milestone:
            db.session.add(ShipmentMilestone(
                shipment_id=shipment.id,
                stage="closed_completed",
                completed_by_id=user_id
            ))

        shipment.shipment_status = "closed"
        shipment.current_stage = "closed_completed"
        
        db.session.commit()
        return jsonify({"success": True, "message": "Shipment closed successfully."}), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# =========================================================
# API: EDIT SHIPMENT
# URL: /api/shipments/<int:shipment_id>/edit
# =========================================================

@api_bp.route(
    "/shipments/<int:shipment_id>/edit",
    methods=["POST"]
)
@jwt_required()
def api_edit_shipment(shipment_id):
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        shipment = Shipment.query.get_or_404(shipment_id)

        if shipment.shipment_status == "closed" and getattr(user, "role", None) != "admin":
            return jsonify({"success": False, "message": "Closed shipments can be edited only by an Admin."}), 403

        # డేటాను JSON లేదా Form నుంచి అందుకోవడం
        data = request.get_json(silent=True) or request.form

        origin = str(data.get("origin") or "").strip()
        destination = str(data.get("destination") or "").strip()
        cargo_description = str(data.get("cargo_description") or "").strip()
        cargo_weight_volume = str(data.get("cargo_weight_volume") or "").strip()
        etd_value = str(data.get("etd") or "").strip()
        eta_value = str(data.get("eta") or "").strip()

        if not origin or not destination or not cargo_description:
            return jsonify({"success": False, "message": "Origin, Destination, and Cargo Description are required."}), 400

        etd = None
        eta = None
        
        try:
            if etd_value:
                etd = datetime.strptime(etd_value.replace('T', ' '), "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                etd = datetime.strptime(etd_value, "%Y-%m-%d")
            except ValueError:
                pass

        try:
            if eta_value:
                eta = datetime.strptime(eta_value.replace('T', ' '), "%Y-%m-%d %H:%M")
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

        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": f"Shipment {shipment.shipment_reference} updated successfully.",
            "shipment": {
                "id": shipment.id,
                "shipment_reference": shipment.shipment_reference,
                "origin": shipment.origin,
                "destination": shipment.destination,
                "cargo_description": shipment.cargo_description,
                "cargo_weight_volume": shipment.cargo_weight_volume,
                "etd": shipment.etd.strftime('%Y-%m-%d %H:%M') if shipment.etd else None,
                "eta": shipment.eta.strftime('%Y-%m-%d %H:%M') if shipment.eta else None,
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": "Unable to update shipment."}), 500
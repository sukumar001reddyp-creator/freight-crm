from datetime import datetime, timezone  # ఇక్కడ datetime మరియు timezone ఇంపోర్ట్ చేసాము
from flask import Blueprint, request, jsonify
from flask_login import login_user
from app import db
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from app.models import User
from app.models import Client, Shipment, Enquiry, Quotation, ClientStatusHistory

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

        # Tags మరియు Services ని సేఫ్‌గా లిస్ట్ లాగా మార్చడం
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

        # Tags మరియు Services ని సేఫ్‌గా లిస్ట్ లాగా మార్చడం
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
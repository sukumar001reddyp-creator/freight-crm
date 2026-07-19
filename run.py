import os

from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():

    # =========================================================================
    # DYNAMIC DBL-ALTER TRIGGER FOR ALL NEW FIELDS (Change Request Updates)
    # =========================================================================
    from sqlalchemy import text
    
    # 1. SHIPMENTS TABLE NEW COLUMNS (If any are pending)
    shipment_cols = [
        "hbl_no", "shipper_name", "consignee_address", 
        "container_no", "container_type", "shipping_line", 
        "vessel", "cargo_details", "volume", "status",
        "etd", "eta"
    ]
    for col in shipment_cols:
        try:
            db.session.execute(text(f"ALTER TABLE shipments ADD COLUMN {col} TEXT;"))
            db.session.commit()
            print(f">>> Added column {col} to shipments successfully!")
        except Exception:
            db.session.rollback()

    # 2. CLIENTS TABLE NEW COLUMNS (Section 2.2 Fields)
    client_cols = [
        "secondary_contact_details", "company_registration_number",
        "tax_vat_number", "license_number", "payment_terms"
    ]
    for col in client_cols:
        try:
            # SQLite handles JSON as TEXT internally
            db.session.execute(text(f"ALTER TABLE clients ADD COLUMN {col} TEXT;"))
            db.session.commit()
            print(f">>> Added column {col} to clients successfully!")
        except Exception:
            db.session.rollback()

    # 3. ENQUIRIES TABLE NEW COLUMNS (Section 3.1 Fields)
    enquiry_cols = [
        "expected_timeline", "incoterms", "additional_instructions",
        "equipment_type", "total_pieces", "weight_kg", "volume_cbm", "sales_coordinator_id"
    ]
    for col in enquiry_cols:
        try:
            db.session.execute(text(f"ALTER TABLE enquiries ADD COLUMN {col} TEXT;"))
            db.session.commit()
            print(f">>> Added column {col} to enquiries successfully!")
        except Exception:
            db.session.rollback()

    # 4. QUOTATIONS TABLE NEW COLUMNS (Section 4.1 & 4.2 Fields)
    quotation_cols = [
        "shipping_line_airline", "no_of_containers", "container_type_quota",
        "etd", "cutoff_date_documentation", "cutoff_date_cargo",
        "free_time_days", "transit_time_days", "incoterms", "hs_code",
        "cost_breakdown", "payment_terms", "remarks_terms"
    ]
    for col in quotation_cols:
        try:
            db.session.execute(text(f"ALTER TABLE quotations ADD COLUMN {col} TEXT;"))
            db.session.commit()
            print(f">>> Added column {col} to quotations successfully!")
        except Exception:
            db.session.rollback()

    # Create missing tables safely
    db.create_all()

    # Create default admin only if missing
    admin_email = "admin@freightcrm.com"

    admin = User.query.filter_by(
        email=admin_email
    ).first()

    if not admin:
        admin = User(
            full_name="CRM Administrator",
            email=admin_email,
            role="admin",
            is_active_user=True
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
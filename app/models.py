from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# USER MODEL
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="sales_executive")
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_user

    @property
    def role_label(self):
        labels = {
            "admin": "Admin",
            "sales_executive": "Sales Executive",
            "operations_team": "Operations Team",
            "management_viewer": "Management / Viewer",
        }
        return labels.get(self.role, self.role)

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =========================================================
# CLIENT MODEL
# =========================================================

class Client(db.Model):
    __tablename__ = "clients"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    
    # Auto-generated client reference (e.g., CLT-2026-000001)
    client_reference = db.Column(db.String(50), unique=True, nullable=True, index=True)
    
    company_name = db.Column(db.String(200), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="lead", index=True)
    pipeline_stage = db.Column(db.String(50), nullable=True, index=True)
    contact_person_name = db.Column(db.String(150), nullable=False)
    designation = db.Column(db.String(150), nullable=True)
    primary_phone = db.Column(db.String(50), nullable=False, index=True)
    secondary_phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(180), nullable=False, index=True)
    website_url = db.Column(db.String(300), nullable=True)
    address_line_1 = db.Column(db.String(300), nullable=False)
    address_line_2 = db.Column(db.String(300), nullable=True)
    industry_sector = db.Column(db.String(150), nullable=True)
    services_needed = db.Column(db.JSON, nullable=False, default=list)

    # NEW FIELDS FROM CHANGE REQUEST (SECTION 2.2)
    secondary_contact_details = db.Column(db.JSON, nullable=True)
    company_registration_number = db.Column(db.String(100), nullable=True)
    tax_vat_number = db.Column(db.String(100), nullable=True)
    license_number = db.Column(db.String(100), nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)

    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lead_source = db.Column(db.String(100), nullable=True)
    date_added = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    last_contact_date = db.Column(db.Date, nullable=True)
    next_follow_up_date = db.Column(db.Date, nullable=True, index=True)
    priority_level = db.Column(db.String(20), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.JSON, nullable=False, default=list)
    is_archived = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], backref=db.backref("assigned_clients", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_id], backref=db.backref("created_clients", lazy=True))
    
    audit_logs = db.relationship("ClientAuditLog", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientAuditLog.created_at.desc()")
    status_history = db.relationship("ClientStatusHistory", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientStatusHistory.changed_at.desc()")
    pipeline_history = db.relationship("ClientPipelineHistory", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientPipelineHistory.moved_at.desc()")
    attachments = db.relationship("ClientAttachment", back_populates="client", cascade="all, delete-orphan", lazy=True)
    activities = db.relationship("ClientActivity", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientActivity.activity_date.desc()")
    client_notes = db.relationship("ClientNote", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientNote.created_at.desc()")
    tasks = db.relationship("ClientTask", back_populates="client", cascade="all, delete-orphan", lazy=True, order_by="ClientTask.due_date.asc()")

    @property
    def status_label(self):
        labels = {
            "lead": "Lead / Prospect",
            "new": "New Client",
            "active": "Active / Existing Client",
            "key": "Key / Strategic Client",
            "at_risk": "At-Risk Client",
            "dormant": "Dormant / Inactive Client",
            "churned": "Churned / Lost Client",
            "reactivated": "Reactivated / Win-Back Client",
            "referral": "Referral Client",
        }
        return labels.get(self.status, self.status)

    @property
    def priority_label(self):
        return self.priority_level.title() if self.priority_level else "Not Set"

    def __repr__(self):
        return f"<Client {self.company_name}>"


# =========================================================
# CLIENT PIPELINE & TRAILS MODELS
# =========================================================

class ClientPipelineHistory(db.Model):
    __tablename__ = "client_pipeline_history"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    other_client_name = db.Column(db.String(200), nullable=True)
    old_stage = db.Column(db.String(50), nullable=True, index=True)
    new_stage = db.Column(db.String(50), nullable=False, index=True)
    remarks = db.Column(db.Text, nullable=True)
    moved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    moved_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    client = db.relationship("Client", back_populates="pipeline_history")
    moved_by = db.relationship("User", foreign_keys=[moved_by_id])


class ClientStatusHistory(db.Model):
    __tablename__ = "client_status_history"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    changed_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    remarks = db.Column(db.Text, nullable=True)

    client = db.relationship("Client", back_populates="status_history")
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])


class ClientAttachment(db.Model):
    __tablename__ = "client_attachments"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    client = db.relationship("Client", back_populates="attachments")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])


class ClientActivity(db.Model):
    __tablename__ = "client_activities"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type = db.Column(db.String(50), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    activity_date = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    client = db.relationship("Client", back_populates="activities")
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class ClientNote(db.Model):
    __tablename__ = "client_notes"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    note_text = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = db.relationship("Client", back_populates="client_notes")
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class ClientTask(db.Model):
    __tablename__ = "client_tasks"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    task_type = db.Column(db.String(50), default="follow_up", nullable=False, index=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    priority = db.Column(db.String(20), default="medium", nullable=False, index=True)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = db.relationship("Client", back_populates="tasks")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class ClientAuditLog(db.Model):
    __tablename__ = "client_audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    client = db.relationship("Client", back_populates="audit_logs")
    performed_by = db.relationship("User", foreign_keys=[performed_by_id])


# =========================================================
# ENQUIRY MODEL
# =========================================================

class Enquiry(db.Model):
    __tablename__ = "enquiries"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    enquiry_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # ఇక్కడ అన్ని ఫీల్డ్స్ ఒకేసారి కరెక్ట్‌గా ఉన్నాయి
    enquiry_date = db.Column(db.Date, nullable=False, default=lambda: utc_now().date(), index=True)
    expected_timeline = db.Column(db.String(150), nullable=True)
    incoterms = db.Column(db.String(50), nullable=True)
    additional_instructions = db.Column(db.Text, nullable=True)
    
    origin = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    origin_port = db.Column(db.String(200), nullable=True)
    destination_port = db.Column(db.String(200), nullable=True)
    mode_of_shipment = db.Column(db.String(50), nullable=False, index=True)
    equipment_type = db.Column(db.String(50), nullable=True)
    
    cargo_description = db.Column(db.Text, nullable=False)
    total_pieces = db.Column(db.Integer, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    volume_cbm = db.Column(db.Float, nullable=True)
    cargo_weight_volume = db.Column(db.String(150), nullable=True)

    handled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sales_coordinator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="waiting_admin", index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    client = db.relationship("Client", foreign_keys=[client_id])
    handled_by = db.relationship("User", foreign_keys=[handled_by_id])
    sales_coordinator = db.relationship("User", foreign_keys=[sales_coordinator_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


    def __repr__(self):
        return f"<Enquiry {self.enquiry_reference}>"


# =========================================================
# QUOTATION MODEL
# =========================================================

class Quotation(db.Model):
    __tablename__ = "quotations"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    enquiry_id = db.Column(
    db.Integer,
    db.ForeignKey("enquiries.id", ondelete="RESTRICT"),
    nullable=True,
    index=True
)
    client_id = db.Column(
    db.Integer,
    db.ForeignKey("clients.id", ondelete="RESTRICT"),
    nullable=True,
    index=True
)
    other_client_name = db.Column(db.String(200), nullable=True)
    quotation_amount = db.Column(db.Numeric(15, 2), nullable=False)
    currency = db.Column(db.String(10), nullable=False, index=True)
    validity_date = db.Column(db.Date, nullable=False, index=True)
    
    # Document fields
    document_original_filename = db.Column(db.String(255), nullable=True)
    document_stored_filename = db.Column(db.String(255), nullable=True)
    document_file_path = db.Column(db.String(500), nullable=True)
    
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # 4.1 Shipment Details 
    shipping_line_airline = db.Column(db.String(150), nullable=True)
    no_of_containers = db.Column(db.Integer, nullable=True)
    container_type_quota = db.Column(db.String(50), nullable=True)
    etd = db.Column(db.DateTime, nullable=True)
    cutoff_date_documentation = db.Column(db.DateTime, nullable=True)
    cutoff_date_cargo = db.Column(db.DateTime, nullable=True)
    free_time_days = db.Column(db.Integer, nullable=True)
    transit_time_days = db.Column(db.Integer, nullable=True)
    incoterms = db.Column(db.String(50), nullable=True)
    hs_code = db.Column(db.String(50), nullable=True)

    # === NEW COST BREAKDOWN FIELDS (4.2) ===
    ocean_air_freight = db.Column(db.Float, default=0.0)
    origin_charges = db.Column(db.Float, default=0.0)
    destination_charges = db.Column(db.Float, default=0.0)
    insurance_charges = db.Column(db.Float, default=0.0)
    other_surcharges = db.Column(db.Float, default=0.0)
    payment_terms = db.Column(db.String(100), nullable=True)

    # Remarks / Terms & Conditions
    remarks_terms = db.Column(db.Text, nullable=True)
    origin = db.Column(
    db.String(200),
    nullable=True
)
    origin_port = db.Column(db.String(200), nullable=True)
    destination_port = db.Column(db.String(200), nullable=True)
    
    destination = db.Column(
    db.String(200),
    nullable=True
)

    mode_of_shipment = db.Column(
    db.String(50),
    nullable=True
)

    cargo_description = db.Column(
    db.Text,
    nullable=True
)

    cargo_weight_volume = db.Column(
    db.String(100),
    nullable=True
)

    # Relationships
    enquiry = db.relationship("Enquiry", foreign_keys=[enquiry_id])
    client = db.relationship(
    "Client",
    foreign_keys=[client_id]
)
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Quotation {self.quotation_number}>"

# =========================================================
# SHIPMENT & OPERATIONAL MODULES (PRESERVED)
# =========================================================

class ShipmentPartyDetails(db.Model):
    __tablename__ = "shipment_party_details"
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey("enquiries.id", ondelete="RESTRICT"), nullable=True, index=True)

    agent_name = db.Column(db.String(255), nullable=False)
    agent_country = db.Column(db.String(120), nullable=False)
    agent_contact_person = db.Column(db.String(255), nullable=False)
    agent_phone = db.Column(db.String(50), nullable=False)
    agent_email = db.Column(db.String(255), nullable=False)
    agent_reference = db.Column(db.String(255), nullable=True)
    shipper_name = db.Column(db.String(255), nullable=False)
    shipper_address = db.Column(db.Text, nullable=False)
    shipper_contact_person = db.Column(db.String(255), nullable=False)
    shipper_phone = db.Column(db.String(50), nullable=False)
    consignee_name = db.Column(db.String(255), nullable=False)
    consignee_address = db.Column(db.Text, nullable=False)
    consignee_contact_person = db.Column(db.String(255), nullable=False)
    consignee_phone = db.Column(db.String(50), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    quotation = db.relationship("Quotation", foreign_keys=[quotation_id])
    enquiry = db.relationship("Enquiry", foreign_keys=[enquiry_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class Shipment(db.Model):
    __tablename__ = "shipments"
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    shipment_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    @property
    def shipment_id(self):
        return self.shipment_reference

    enquiry_id = db.Column(
    db.Integer,
    db.ForeignKey("enquiries.id"),
    nullable=True
)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True)

    client_id = db.Column(
    db.Integer,
    db.ForeignKey("clients.id"),
    nullable=True
)

    other_client_name = db.Column(
    db.String(200),
    nullable=True
)
    origin = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    mode_of_shipment = db.Column(db.String(50), nullable=False, index=True)
    cargo_description = db.Column(db.Text, nullable=False)
    cargo_weight_volume = db.Column(db.String(150), nullable=True)
    shipment_status = db.Column(db.String(30), nullable=False, default="active", index=True)
    current_stage = db.Column(db.String(50), nullable=False, default="booked", index=True)
    handled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    hbl_no = db.Column(db.String(100), unique=True, nullable=True)
    shipper_name = db.Column(db.String(255), nullable=True)
    consignee_address = db.Column(db.Text, nullable=True)
    container_no = db.Column(db.String(50), nullable=True)
    container_type = db.Column(db.String(20), default="40HC")
    shipping_line = db.Column(db.String(100), default="MAERSK")
    vessel = db.Column(db.String(100), nullable=True)
    cargo_details = db.Column(db.String(255), nullable=True)
    volume = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), default="pending")
    etd = db.Column(db.DateTime, nullable=True)
    eta = db.Column(db.DateTime, nullable=True)

    enquiry = db.relationship("Enquiry", foreign_keys=[enquiry_id])
    quotation = db.relationship("Quotation", foreign_keys=[quotation_id])
    client = db.relationship("Client", foreign_keys=[client_id], backref=db.backref("shipments", lazy=True))
    handled_by = db.relationship("User", foreign_keys=[handled_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class ShipmentMilestone(db.Model):
    __tablename__ = "shipment_milestones"
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = db.Column(db.String(50), nullable=False, index=True)
    remarks = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    shipment = db.relationship("Shipment", foreign_keys=[shipment_id])
    completed_by = db.relationship("User", foreign_keys=[completed_by_id])
    __table_args__ = (db.UniqueConstraint("shipment_id", "stage", name="uq_shipment_stage"),)


class ShipmentDocument(db.Model):
    __tablename__ = "shipment_documents"
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False, index=True)
    document_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    remarks = db.Column(db.Text, nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    shipment = db.relationship("Shipment", foreign_keys=[shipment_id])
    received_by = db.relationship("User", foreign_keys=[received_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    __table_args__ = (db.UniqueConstraint("shipment_id", "document_type", name="uq_shipment_document_type"),)


class ShipmentCustomsClearance(db.Model):
    __tablename__ = "shipment_customs_clearances"
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    clearance_required = db.Column(db.Boolean, nullable=False, default=False, index=True)
    clearance_status = db.Column(db.String(30), nullable=False, default="not_required", index=True)
    clearing_agent_name = db.Column(db.String(255), nullable=True)
    clearance_date = db.Column(db.Date, nullable=True, index=True)
    remarks = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    shipment = db.relationship("Shipment", foreign_keys=[shipment_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


class ShipmentClosure(db.Model):
    __tablename__ = "shipment_closures"
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    closing_status = db.Column(db.String(30), nullable=False, index=True)
    closing_date = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    closing_notes = db.Column(db.Text, nullable=True)
    document_archive_confirmed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    client_feedback = db.Column(db.Text, nullable=True)
    client_rating = db.Column(db.Integer, nullable=True)
    closed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    shipment = db.relationship("Shipment", foreign_keys=[shipment_id])
    closed_by = db.relationship("User", foreign_keys=[closed_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


# =========================================================
# SYSTEM SERVICES MODELS
# =========================================================

class ClientPortalUser(db.Model):
    __tablename__ = "client_portal_users"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    client = db.relationship("Client", backref=db.backref("portal_account", uselist=False))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="waiting_admin", nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    admin_reply = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    client = db.relationship("Client", foreign_keys=[client_id])


class SupportMessage(db.Model):
    __tablename__ = "support_messages"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    ticket = db.relationship("SupportTicket", backref=db.backref("messages", lazy=True, order_by="SupportMessage.created_at.asc()", cascade="all, delete-orphan"))


class BackupLog(db.Model):
    __tablename__ = "backup_logs"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    file_id = db.Column(db.String(255), nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

class ShipmentTask(db.Model):
    __tablename__ = "shipment_tasks"
    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    
    # Relationships
    shipment = db.relationship("Shipment", backref=db.backref("tasks", cascade="all, delete-orphan", lazy=True))

from app import db

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    maintenance = db.Column(db.Boolean, default=False)
    app_env = db.Column(db.String(50), default="production")
    base_currency = db.Column(db.String(10), default="KWD")
    alert_email = db.Column(db.String(100), default="alerts@crm.com")
    backup_interval = db.Column(db.String(20), default="daily")

    @staticmethod
    def create(filename, status, file_id=None, error=None):
        log = BackupLog(filename=filename, status=status, file_id=file_id, error=error)
        db.session.add(log)
        db.session.commit()
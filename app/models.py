from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from app import db, login_manager


def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# USER MODEL
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    full_name = db.Column(
        db.String(120),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        nullable=False,
        default="sales_executive"
    )

    is_active_user = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

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

        return labels.get(
            self.role,
            self.role
        )

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(
        User,
        int(user_id)
    )


# =========================================================
# CLIENT MODEL
# Document Section 3 — Add Client Full Field List
# =========================================================

class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    # Permanent audit history
    audit_logs = db.relationship(
        "ClientAuditLog",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClientAuditLog.created_at.desc()"
    )
    # -----------------------------------------------------
    # BASIC CLIENT DETAILS
    # -----------------------------------------------------

    company_name = db.Column(
        db.String(200),
        nullable=False,
        index=True
    )

    category = db.Column(
        db.String(100),
        nullable=False,
        index=True
    )

    status = db.Column(
        db.String(50),
        nullable=False,
        default="lead",
        index=True
    )

    contact_person_name = db.Column(
        db.String(150),
        nullable=False
    )

    designation = db.Column(
        db.String(150),
        nullable=True
    )

    primary_phone = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    secondary_phone = db.Column(
        db.String(50),
        nullable=True
    )

    email = db.Column(
        db.String(180),
        nullable=False,
        index=True
    )

    website_url = db.Column(
        db.String(300),
        nullable=True
    )

    address_line_1 = db.Column(
        db.String(300),
        nullable=False
    )

    address_line_2 = db.Column(
        db.String(300),
        nullable=True
    )

    industry_sector = db.Column(
        db.String(150),
        nullable=True
    )

    # Multi-select services stored as JSON list
    services_needed = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # -----------------------------------------------------
    # OWNERSHIP / SALES DETAILS
    # -----------------------------------------------------

    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    lead_source = db.Column(
        db.String(100),
        nullable=True
    )

    date_added = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )

    last_contact_date = db.Column(
        db.Date,
        nullable=True
    )

    next_follow_up_date = db.Column(
        db.Date,
        nullable=True,
        index=True
    )

    priority_level = db.Column(
        db.String(20),
        nullable=True,
        index=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    # Custom labels / tags
    tags = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # -----------------------------------------------------
    # SYSTEM FIELDS
    # -----------------------------------------------------

    is_archived = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    assigned_to = db.relationship(
        "User",
        foreign_keys=[assigned_to_id],
        backref=db.backref(
            "assigned_clients",
            lazy=True
        )
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id],
        backref=db.backref(
            "created_clients",
            lazy=True
        )
    )

    status_history = db.relationship(
        "ClientStatusHistory",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClientStatusHistory.changed_at.desc()"
    )

    attachments = db.relationship(
        "ClientAttachment",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True
    )
    activities = db.relationship(
        "ClientActivity",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClientActivity.activity_date.desc()"
    )
    client_notes = db.relationship(
        "ClientNote",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClientNote.created_at.desc()"
    )
    tasks = db.relationship(
        "ClientTask",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClientTask.due_date.asc()"
    )

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

        return labels.get(
            self.status,
            self.status
        )

    @property
    def priority_label(self):
        if not self.priority_level:
            return "Not Set"

        return self.priority_level.title()

    def __repr__(self):
        return f"<Client {self.company_name}>"


# =========================================================
# CLIENT STATUS HISTORY
# Document requires timestamped status changes
# =========================================================

class ClientStatusHistory(db.Model):
    __tablename__ = "client_status_history"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    old_status = db.Column(
        db.String(50),
        nullable=True
    )

    new_status = db.Column(
        db.String(50),
        nullable=False
    )

    changed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    changed_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )

    remarks = db.Column(
        db.Text,
        nullable=True
    )

    client = db.relationship(
        "Client",
        back_populates="status_history"
    )

    changed_by = db.relationship(
        "User",
        foreign_keys=[changed_by_id]
    )

    def __repr__(self):
        return (
            f"<ClientStatusHistory "
            f"{self.old_status} -> {self.new_status}>"
        )


# =========================================================
# CLIENT ATTACHMENTS
# Document: PDF, JPG, DOCX
# =========================================================

class ClientAttachment(db.Model):
    __tablename__ = "client_attachments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False
    )

    stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True
    )

    file_path = db.Column(
        db.String(500),
        nullable=False
    )

    file_type = db.Column(
        db.String(50),
        nullable=True
    )

    uploaded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    client = db.relationship(
        "Client",
        back_populates="attachments"
    )

    uploaded_by = db.relationship(
        "User",
        foreign_keys=[uploaded_by_id]
    )

    def __repr__(self):
        return (
            f"<ClientAttachment "
            f"{self.original_filename}>"
        )
    # =========================================================
# CLIENT ACTIVITY / COMMUNICATION LOG
# Document Section 5:
# Log Communication / Activity (Call, Email, Meeting)
# =========================================================

class ClientActivity(db.Model):
    __tablename__ = "client_activities"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    activity_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    subject = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    activity_date = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    client = db.relationship(
        "Client",
        back_populates="activities"
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    @property
    def activity_type_label(self):
        labels = {
            "call": "Call",
            "email": "Email",
            "meeting": "Meeting",
        }

        return labels.get(
            self.activity_type,
            self.activity_type.title()
        )

    def __repr__(self):
        return (
            f"<ClientActivity "
            f"{self.activity_type} - "
            f"{self.subject}>"
        )
    # =========================================================
# CLIENT NOTE / REMARK
# =========================================================

class ClientNote(db.Model):
    __tablename__ = "client_notes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    note_text = db.Column(
        db.Text,
        nullable=False
    )

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    client = db.relationship(
        "Client",
        back_populates="client_notes"
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    def __repr__(self):
        return (
            f"<ClientNote "
            f"client_id={self.client_id}>"
        )

    # =========================================================
# CLIENT TASK / FOLLOW-UP REMINDER
# =========================================================

class ClientTask(db.Model):
    __tablename__ = "client_tasks"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    task_type = db.Column(
        db.String(50),
        default="follow_up",
        nullable=False,
        index=True
    )

    due_date = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True
    )

    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    priority = db.Column(
        db.String(20),
        default="medium",
        nullable=False,
        index=True
    )

    status = db.Column(
        db.String(30),
        default="pending",
        nullable=False,
        index=True
    )

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    client = db.relationship(
        "Client",
        back_populates="tasks"
    )

    assigned_to = db.relationship(
        "User",
        foreign_keys=[assigned_to_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    @property
    def task_type_label(self):
        labels = {
            "follow_up": "Follow-Up",
            "call": "Call",
            "email": "Email",
            "meeting": "Meeting",
            "general": "General Task",
        }

        return labels.get(
            self.task_type,
            self.task_type.replace("_", " ").title()
        )

    @property
    def status_label(self):
        labels = {
            "pending": "Pending",
            "in_progress": "In Progress",
            "completed": "Completed",
            "cancelled": "Cancelled",
        }

        return labels.get(
            self.status,
            self.status.replace("_", " ").title()
        )

    @property
    def priority_label(self):
        return self.priority.title()

    def __repr__(self):
        return f"<ClientTask {self.title}>"
    # =========================================================
# CLIENT AUDIT LOG
# Permanent history / trail
# =========================================================

class ClientAuditLog(db.Model):
    __tablename__ = "client_audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Which client?
    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Example:
    # activity
    # note
    # task
    # document
    # status
    action_type = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    # Example:
    # created
    # updated
    # deleted
    # uploaded
    # status_changed
    action = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    # Main heading shown in History
    title = db.Column(
        db.String(255),
        nullable=False
    )

    # Extra information
    description = db.Column(
        db.Text,
        nullable=True
    )

    # User who performed action
    performed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Permanent event time
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )

    # Relationships
    client = db.relationship(
        "Client",
        back_populates="audit_logs"
    )

    performed_by = db.relationship(
        "User",
        foreign_keys=[performed_by_id]
    )

    def __repr__(self):
        return (
            f"<ClientAuditLog "
            f"{self.action_type}: "
            f"{self.action}>"
        )
# =========================================================
# ENQUIRY
# Document Section 4.1 — Step 1
# Every enquiry is linked to an existing Client/Pipeline
# =========================================================

class Enquiry(db.Model):
    __tablename__ = "enquiries"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Auto-generated unique reference
    # Example: ENQ-2026-000001
    enquiry_reference = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True
    )

    # Required linked client
    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    # Auto-filled enquiry date
    enquiry_date = db.Column(
        db.Date,
        nullable=False,
        default=lambda: utc_now().date(),
        index=True
    )

    # Required origin
    origin = db.Column(
        db.String(255),
        nullable=False
    )

    # Required destination
    destination = db.Column(
        db.String(255),
        nullable=False
    )

    # Required:
    # air_freight
    # sea_freight
    # land_freight
    mode_of_shipment = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    # Required nature/type of goods
    cargo_description = db.Column(
        db.Text,
        nullable=False
    )

    # Optional:
    # Examples: 2500 kg, 18 CBM, 2 containers
    cargo_weight_volume = db.Column(
        db.String(150),
        nullable=True
    )

    # Required staff owner / Sales Executive
    handled_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Internal workflow state.
    # Needed later for quotation/conversion flow.
    status = db.Column(
        db.String(30),
        nullable=False,
        default="open",
        index=True
    )

    # Audit fields
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    client = db.relationship(
        "Client",
        foreign_keys=[client_id]
    )

    handled_by = db.relationship(
        "User",
        foreign_keys=[handled_by_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    def __repr__(self):
        return (
            f"<Enquiry "
            f"{self.enquiry_reference}>"
        )
    # =========================================================
# QUOTATION MODEL
#
# Document Section 4.2:
# Quotation & Approval Status
#
# One quotation is created against an enquiry.
# Status flow:
# pending -> approved OR rejected
# =========================================================

class Quotation(db.Model):

    __tablename__ = "quotations"

    # -----------------------------------------------------
    # PRIMARY KEY
    # -----------------------------------------------------

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    # -----------------------------------------------------
    # AUTO-GENERATED QUOTATION NUMBER
    #
    # Example:
    # QUO-2026-000001
    # -----------------------------------------------------

    quotation_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # LINK TO ENQUIRY
    #
    # Every quotation belongs to one enquiry.
    # -----------------------------------------------------

    enquiry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "enquiries.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # QUOTATION AMOUNT
    #
    # Numeric(15, 2):
    # Example:
    # 1250.00
    # 45000.50
    #
    # Money ki Float use cheyyatledu.
    # -----------------------------------------------------

    quotation_amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )


    # -----------------------------------------------------
    # CURRENCY
    #
    # Examples:
    # USD
    # KWD
    # AED
    # -----------------------------------------------------

    currency = db.Column(
        db.String(10),
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # VALIDITY DATE
    #
    # Quotation expiry date.
    # -----------------------------------------------------

    validity_date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # OPTIONAL QUOTATION DOCUMENT
    #
    # PDF path matrame DB lo save chestham.
    # Actual file disk/storage lo untundi.
    # -----------------------------------------------------

    document_original_filename = db.Column(
        db.String(255),
        nullable=True
    )

    document_stored_filename = db.Column(
        db.String(255),
        nullable=True
    )

    document_file_path = db.Column(
        db.String(500),
        nullable=True
    )


    # -----------------------------------------------------
    # QUOTATION STATUS
    #
    # Allowed:
    # pending
    # approved
    # rejected
    # -----------------------------------------------------

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending",
        index=True
    )


    # -----------------------------------------------------
    # REJECTION REASON
    #
    # Required by application logic only when:
    # status == "rejected"
    # -----------------------------------------------------

    rejection_reason = db.Column(
        db.Text,
        nullable=True
    )


    # -----------------------------------------------------
    # APPROVAL DETAILS
    #
    # Captured only when:
    # status == "approved"
    # -----------------------------------------------------

    approved_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    approved_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )


    # -----------------------------------------------------
    # AUDIT FIELDS
    # -----------------------------------------------------

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )


    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    enquiry = db.relationship(
        "Enquiry",
        foreign_keys=[enquiry_id]
    )

    approved_by = db.relationship(
        "User",
        foreign_keys=[approved_by_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )


    # -----------------------------------------------------
    # DEBUG REPRESENTATION
    # -----------------------------------------------------

    def __repr__(self):

        return (
            f"<Quotation "
            f"{self.quotation_number}>"
        )
# =========================================================
# SHIPMENT PARTY DETAILS MODEL
#
# Approved Quotation ->
# Agent + Shipper + Consignee Details ->
# Shipment Conversion
# =========================================================

class ShipmentPartyDetails(db.Model):

    __tablename__ = "shipment_party_details"

    # -----------------------------------------------------
    # PRIMARY KEY
    # -----------------------------------------------------

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # -----------------------------------------------------
    # LINK TO APPROVED QUOTATION
    #
    # One quotation = one party-details record
    # -----------------------------------------------------

    quotation_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "quotations.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True
    )

    # -----------------------------------------------------
    # LINK TO ENQUIRY
    # -----------------------------------------------------

    enquiry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "enquiries.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )

    # =====================================================
    # AGENT DETAILS
    # =====================================================

    agent_name = db.Column(
        db.String(255),
        nullable=False
    )

    agent_country = db.Column(
        db.String(120),
        nullable=False
    )

    agent_contact_person = db.Column(
        db.String(255),
        nullable=False
    )

    agent_phone = db.Column(
        db.String(50),
        nullable=False
    )

    agent_email = db.Column(
        db.String(255),
        nullable=False
    )

    agent_reference = db.Column(
        db.String(255),
        nullable=True
    )

    # =====================================================
    # SHIPPER DETAILS
    # =====================================================

    shipper_name = db.Column(
        db.String(255),
        nullable=False
    )

    shipper_address = db.Column(
        db.Text,
        nullable=False
    )

    shipper_contact_person = db.Column(
        db.String(255),
        nullable=False
    )

    shipper_phone = db.Column(
        db.String(50),
        nullable=False
    )

    # =====================================================
    # CONSIGNEE DETAILS
    # =====================================================

    consignee_name = db.Column(
        db.String(255),
        nullable=False
    )

    consignee_address = db.Column(
        db.Text,
        nullable=False
    )

    consignee_contact_person = db.Column(
        db.String(255),
        nullable=False
    )

    consignee_phone = db.Column(
        db.String(50),
        nullable=False
    )

    # =====================================================
    # AUDIT FIELDS
    # =====================================================

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    quotation = db.relationship(
        "Quotation",
        foreign_keys=[quotation_id]
    )

    enquiry = db.relationship(
        "Enquiry",
        foreign_keys=[enquiry_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )

    # =====================================================
    # DEBUG REPRESENTATION
    # =====================================================

    def __repr__(self):

        return (
            f"<ShipmentPartyDetails "
            f"Quotation={self.quotation_id}>"
        )
    # =========================================================
# SHIPMENT MODEL
#
# Approved Quotation -> Shipment Conversion
#
# Workflow:
# Enquiry -> Quotation -> Approved -> Shipment
# =========================================================

class Shipment(db.Model):

    __tablename__ = "shipments"

    # -----------------------------------------------------
    # PRIMARY KEY
    # -----------------------------------------------------

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    # -----------------------------------------------------
    # AUTO-GENERATED SHIPMENT REFERENCE
    #
    # Example:
    # SHP-2026-000001
    # -----------------------------------------------------

    shipment_reference = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # SOURCE ENQUIRY
    # -----------------------------------------------------

    enquiry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "enquiries.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        unique=True,
        index=True
    )


    # -----------------------------------------------------
    # APPROVED QUOTATION
    # -----------------------------------------------------

    quotation_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "quotations.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        unique=True,
        index=True
    )


    # -----------------------------------------------------
    # CLIENT
    #
    # Auto-filled from original enquiry.
    # -----------------------------------------------------

    client_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "clients.id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # SHIPMENT ROUTE
    # -----------------------------------------------------

    origin = db.Column(
        db.String(255),
        nullable=False
    )

    destination = db.Column(
        db.String(255),
        nullable=False
    )


    # -----------------------------------------------------
    # MODE OF SHIPMENT
    #
    # air_freight
    # sea_freight
    # land_freight
    # -----------------------------------------------------

    mode_of_shipment = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # CARGO DETAILS
    # -----------------------------------------------------

    cargo_description = db.Column(
        db.Text,
        nullable=False
    )

    cargo_weight_volume = db.Column(
        db.String(150),
        nullable=True
    )


    # -----------------------------------------------------
    # SHIPMENT STATUS
    #
    # Initial:
    # active
    #
    # Later workflow can use:
    # active
    # in_transit
    # delivered
    # closed
    # -----------------------------------------------------

    shipment_status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True
    )


    # -----------------------------------------------------
    # HANDLED BY
    # -----------------------------------------------------

    handled_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )


    # -----------------------------------------------------
    # AUDIT FIELDS
    # -----------------------------------------------------

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )


    # -----------------------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------------------

    enquiry = db.relationship(
        "Enquiry",
        foreign_keys=[enquiry_id]
    )

    quotation = db.relationship(
        "Quotation",
        foreign_keys=[quotation_id]
    )

    client = db.relationship(
        "Client",
        foreign_keys=[client_id]
    )

    handled_by = db.relationship(
        "User",
        foreign_keys=[handled_by_id]
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )


    # -----------------------------------------------------
    # DEBUG REPRESENTATION
    # -----------------------------------------------------

    def __repr__(self):

        return (
            f"<Shipment "
            f"{self.shipment_reference}>"
        )
    # =========================================================
# SHIPMENT MILESTONE MODEL
#
# Operational workflow timeline:
#
# 1. Booking Confirmed
# 2. Pickup
# 3. Origin Handling
# 4. In Transit
# 5. Arrival
# 6. Customs Clearance
# 7. Delivery
# 8. Closed
# =========================================================

class ShipmentMilestone(db.Model):

    __tablename__ = "shipment_milestones"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # -----------------------------------------
    # LINKED SHIPMENT
    # -----------------------------------------

    shipment_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "shipments.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # -----------------------------------------
    # WORKFLOW STAGE KEY
    #
    # booking_confirmed
    # pickup
    # origin_handling
    # in_transit
    # arrival
    # customs_clearance
    # delivery
    # closed
    # -----------------------------------------

    stage = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    # -----------------------------------------
    # OPTIONAL REMARKS
    # -----------------------------------------

    remarks = db.Column(
        db.Text,
        nullable=True
    )

    # -----------------------------------------
    # COMPLETION INFORMATION
    # -----------------------------------------

    completed_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    completed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # -----------------------------------------
    # AUDIT
    # -----------------------------------------

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    # -----------------------------------------
    # RELATIONSHIPS
    # -----------------------------------------

    shipment = db.relationship(
        "Shipment",
        foreign_keys=[shipment_id]
    )

    completed_by = db.relationship(
        "User",
        foreign_keys=[completed_by_id]
    )

    # -----------------------------------------
    # PREVENT SAME STAGE DUPLICATE
    # -----------------------------------------

    __table_args__ = (
        db.UniqueConstraint(
            "shipment_id",
            "stage",
            name="uq_shipment_stage"
        ),
    )

    def __repr__(self):

        return (
            f"<ShipmentMilestone "
            f"{self.shipment_id} "
            f"{self.stage}>"
        )
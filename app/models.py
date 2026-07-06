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
import os
import uuid
from datetime import datetime, timezone

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    abort,
    send_from_directory,
)

from flask_login import (
    login_required,
    current_user,
)

from werkzeug.utils import secure_filename

from sqlalchemy import or_

from app import db

from app.models import (
    Client,
    ClientActivity,
    ClientAttachment,
    ClientAuditLog,
    ClientNote,
    ClientStatusHistory,
    ClientTask,
    User,
)


clients_bp = Blueprint(
    "clients",
    __name__,
    url_prefix="/clients"
)


# =========================================================
# DOCUMENT-MATCHED OPTIONS
# =========================================================

CLIENT_CATEGORIES = [
    ("existing_client", "Existing Client"),
    ("pipeline", "Pipeline"),
    ("embassy", "Embassy"),
    ("tender", "Tender"),
    ("k_company", "K-Company"),
    ("foreign_agent", "Foreign Agent"),
    ("epc_oil_gas", "EPC Oil & Gas"),
    ("oil_contractor", "Oil Contractor"),
]


CLIENT_STATUSES = [
    ("lead", "Lead / Prospect"),
    ("new", "New Client"),
    ("active", "Active / Existing Client"),
    ("key", "Key / Strategic Client"),
    ("at_risk", "At-Risk Client"),
    ("dormant", "Dormant / Inactive Client"),
    ("churned", "Churned / Lost Client"),
    ("reactivated", "Reactivated / Win-Back Client"),
    ("referral", "Referral Client"),
]


SERVICE_OPTIONS = [
    ("air_freight", "Air Freight"),
    ("sea_freight", "Sea Freight"),
    ("land_freight", "Land Freight"),
    ("customs_clearance", "Customs Clearance"),
    ("warehousing", "Warehousing"),
    ("project_cargo", "Project Cargo"),
]


LEAD_SOURCES = [
    ("referral", "Referral"),
    ("website", "Website"),
    ("cold_call", "Cold Call"),
    ("exhibition", "Exhibition"),
    ("tender_notice", "Tender Notice"),
    ("existing_network", "Existing Network"),
    ("other", "Other"),
]


PRIORITY_LEVELS = [
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
]


ALLOWED_EXTENSIONS = {
    "pdf",
    "jpg",
    "jpeg",
    "docx",
}


# =========================================================
# HELPERS
# =========================================================

def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return None


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_upload_folder():
    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "clients"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    return upload_folder
# =========================================================
# CLIENT PERMANENT AUDIT LOG HELPER
# =========================================================

def log_client_audit(
    client_id,
    action_type,
    action,
    title,
    description=None
):
    """
    Save one permanent client history event.

    Important:
    This function only ADDS the audit row.
    Caller will commit the transaction.
    """

    audit_log = ClientAuditLog(
        client_id=client_id,
        action_type=action_type,
        action=action,
        title=title,
        description=description,
        performed_by_id=current_user.id,
    )

    db.session.add(audit_log)

    return audit_log


def get_form_options():
    owners = (
        User.query
        .filter_by(is_active_user=True)
        .order_by(User.full_name.asc())
        .all()
    )

    return {
        "categories": CLIENT_CATEGORIES,
        "statuses": CLIENT_STATUSES,
        "services": SERVICE_OPTIONS,
        "lead_sources": LEAD_SOURCES,
        "priorities": PRIORITY_LEVELS,
        "owners": owners,
    }


# =========================================================
# CLIENT LIST
# SEARCH + FILTER + SORT + PAGINATION
# =========================================================

@clients_bp.route("/")
@login_required
def client_list():

    # -----------------------------------------
    # URL QUERY PARAMETERS
    # -----------------------------------------

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    assigned_to = request.args.get(
        "assigned_to",
        type=int
    )

    priority = request.args.get(
        "priority",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "newest"
    ).strip()

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1


    # -----------------------------------------
    # BASE QUERY
    # -----------------------------------------

    query = (
        Client.query
        .filter_by(is_archived=False)
    )


    # -----------------------------------------
    # SEARCH
    # -----------------------------------------

    if search:
        search_term = f"%{search}%"

        query = query.filter(
            or_(
                Client.company_name.ilike(
                    search_term
                ),
                Client.contact_person_name.ilike(
                    search_term
                ),
                Client.email.ilike(
                    search_term
                ),
                Client.primary_phone.ilike(
                    search_term
                ),
                Client.industry_sector.ilike(
                    search_term
                ),
            )
        )


    # -----------------------------------------
    # FILTERS
    # -----------------------------------------

    if category:
        query = query.filter(
            Client.category == category
        )

    if status:
        query = query.filter(
            Client.status == status
        )

    if assigned_to:
        query = query.filter(
            Client.assigned_to_id == assigned_to
        )

    if priority:
        query = query.filter(
            Client.priority_level == priority
        )


    # -----------------------------------------
    # SORTING
    # -----------------------------------------

    if sort == "oldest":
        query = query.order_by(
            Client.date_added.asc()
        )

    elif sort == "name_az":
        query = query.order_by(
            Client.company_name.asc()
        )

    elif sort == "name_za":
        query = query.order_by(
            Client.company_name.desc()
        )

    elif sort == "follow_up":
        query = query.order_by(
            Client.next_follow_up_date.asc()
        )

    else:
        query = query.order_by(
            Client.date_added.desc()
        )


    # -----------------------------------------
    # PAGINATION
    # -----------------------------------------

    pagination = query.paginate(
        page=page,
        per_page=10,
        error_out=False
    )

    clients = pagination.items


    # -----------------------------------------
    # OWNERS FOR FILTER
    # -----------------------------------------

    owners = (
        User.query
        .filter_by(is_active_user=True)
        .order_by(User.full_name.asc())
        .all()
    )


    # -----------------------------------------
    # STATS
    # -----------------------------------------

    total_clients = (
        Client.query
        .filter_by(is_archived=False)
        .count()
    )

    active_clients = (
        Client.query
        .filter(
            Client.is_archived.is_(False),
            Client.status.in_([
                "active",
                "key",
                "reactivated",
            ])
        )
        .count()
    )

    lead_clients = (
        Client.query
        .filter(
            Client.is_archived.is_(False),
            Client.status.in_([
                "lead",
                "new",
            ])
        )
        .count()
    )

    at_risk_clients = (
        Client.query
        .filter(
            Client.is_archived.is_(False),
            Client.status == "at_risk"
        )
        .count()
    )


    return render_template(
        "clients/list.html",
        clients=clients,
        pagination=pagination,
        owners=owners,
        categories=CLIENT_CATEGORIES,
        statuses=CLIENT_STATUSES,
        priorities=PRIORITY_LEVELS,
        total_clients=total_clients,
        active_clients=active_clients,
        lead_clients=lead_clients,
        at_risk_clients=at_risk_clients,
        current_search=search,
        current_category=category,
        current_status=status,
        current_assigned_to=assigned_to,
        current_priority=priority,
        current_sort=sort,
    )


# =========================================================
# ADD CLIENT
# =========================================================

@clients_bp.route(
    "/add",
    methods=["GET", "POST"]
)
@login_required
def add_client():

    options = get_form_options()

    if request.method == "POST":

        company_name = request.form.get(
            "company_name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        status = request.form.get(
            "status",
            ""
        ).strip()

        contact_person_name = request.form.get(
            "contact_person_name",
            ""
        ).strip()

        primary_phone = request.form.get(
            "primary_phone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        address_line_1 = request.form.get(
            "address_line_1",
            ""
        ).strip()

        assigned_to_id = request.form.get(
            "assigned_to_id",
            type=int
        )

        services_needed = request.form.getlist(
            "services_needed"
        )


        required_values = [
            company_name,
            category,
            status,
            contact_person_name,
            primary_phone,
            email,
            address_line_1,
            assigned_to_id,
        ]

        if not all(required_values):
            flash(
                "Please complete all required fields.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        valid_categories = {
            value
            for value, label
            in CLIENT_CATEGORIES
        }

        valid_statuses = {
            value
            for value, label
            in CLIENT_STATUSES
        }

        valid_services = {
            value
            for value, label
            in SERVICE_OPTIONS
        }


        if category not in valid_categories:
            flash(
                "Invalid client category selected.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        if status not in valid_statuses:
            flash(
                "Invalid client status selected.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        services_needed = [
            service
            for service in services_needed
            if service in valid_services
        ]


        if not services_needed:
            flash(
                "Select at least one required service.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        assigned_owner = db.session.get(
            User,
            assigned_to_id
        )

        if (
            not assigned_owner
            or not assigned_owner.is_active_user
        ):
            flash(
                "Please select a valid active owner.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        designation = request.form.get(
            "designation",
            ""
        ).strip() or None

        secondary_phone = request.form.get(
            "secondary_phone",
            ""
        ).strip() or None

        website_url = request.form.get(
            "website_url",
            ""
        ).strip() or None

        address_line_2 = request.form.get(
            "address_line_2",
            ""
        ).strip() or None

        industry_sector = request.form.get(
            "industry_sector",
            ""
        ).strip() or None

        lead_source = request.form.get(
            "lead_source",
            ""
        ).strip() or None

        last_contact_date = parse_date(
            request.form.get(
                "last_contact_date"
            )
        )

        next_follow_up_date = parse_date(
            request.form.get(
                "next_follow_up_date"
            )
        )

        priority_level = request.form.get(
            "priority_level",
            ""
        ).strip() or None

        notes = request.form.get(
            "notes",
            ""
        ).strip() or None


        raw_tags = request.form.get(
            "tags",
            ""
        )

        tags = []

        if raw_tags:
            tags = [
                tag.strip()
                for tag in raw_tags.split(",")
                if tag.strip()
            ]

            tags = list(
                dict.fromkeys(tags)
            )


        client = Client(
            company_name=company_name,
            category=category,
            status=status,
            contact_person_name=contact_person_name,
            designation=designation,
            primary_phone=primary_phone,
            secondary_phone=secondary_phone,
            email=email,
            website_url=website_url,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            industry_sector=industry_sector,
            services_needed=services_needed,
            assigned_to_id=assigned_to_id,
            lead_source=lead_source,
            last_contact_date=last_contact_date,
            next_follow_up_date=next_follow_up_date,
            priority_level=priority_level,
            notes=notes,
            tags=tags,
            created_by_id=current_user.id,
        )

        db.session.add(client)
        db.session.flush()


        status_history = ClientStatusHistory(
            client_id=client.id,
            old_status=None,
            new_status=status,
            changed_by_id=current_user.id,
            remarks=(
                "Initial client status "
                "on record creation."
            )
        )

        db.session.add(status_history)


        uploaded_files = request.files.getlist(
            "attachments"
        )

        upload_folder = get_upload_folder()


        for uploaded_file in uploaded_files:

            if (
                not uploaded_file
                or not uploaded_file.filename
            ):
                continue

            if not allowed_file(
                uploaded_file.filename
            ):
                db.session.rollback()

                flash(
                    "Only PDF, JPG, JPEG and DOCX "
                    "attachments are allowed.",
                    "danger"
                )

                return render_template(
                    "clients/add.html",
                    **options
                )


            original_filename = secure_filename(
                uploaded_file.filename
            )

            extension = (
                original_filename
                .rsplit(".", 1)[1]
                .lower()
            )

            stored_filename = (
                f"{uuid.uuid4().hex}.{extension}"
            )

            absolute_path = os.path.join(
                upload_folder,
                stored_filename
            )

            uploaded_file.save(
                absolute_path
            )

            relative_path = os.path.join(
                "uploads",
                "clients",
                stored_filename
            ).replace("\\", "/")


            attachment = ClientAttachment(
                client_id=client.id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=relative_path,
                file_type=extension,
                uploaded_by_id=current_user.id,
            )

            db.session.add(attachment)


        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to save the client record. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "clients/add.html",
                **options
            )


        flash(
            f"{client.company_name} "
            f"was added successfully.",
            "success"
        )

        return redirect(
            url_for(
                "clients.client_list"
            )
        )


    return render_template(
        "clients/add.html",
        **options
    )


# =========================================================
# VIEW CLIENT
# =========================================================

# =========================================================
# CHANGE CLIENT STATUS
# =========================================================

@clients_bp.route(
    "/<int:client_id>/change-status",
    methods=["POST"]
)
@login_required
def change_status(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    new_status = request.form.get(
        "new_status",
        ""
    ).strip()

    remarks = request.form.get(
        "remarks",
        ""
    ).strip() or None

    valid_statuses = {
        value
        for value, label
        in CLIENT_STATUSES
    }

    if new_status not in valid_statuses:
        flash(
            "Invalid client status selected.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    if new_status == client.status:
        flash(
            "Client is already in that status.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    old_status = client.status

    client.status = new_status

    history = ClientStatusHistory(
        client_id=client.id,
        old_status=old_status,
        new_status=new_status,
        changed_by_id=current_user.id,
        remarks=remarks,
    )

    db.session.add(history)

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to update client status.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    flash(
        f"{client.company_name} status updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
    )
# =========================================================
# ADD CLIENT ACTIVITY / COMMUNICATION
# Document requirement:
# Call, Email, Meeting + Activity Timeline
# =========================================================

@clients_bp.route(
    "/<int:client_id>/activities/add",
    methods=["POST"]
)
@login_required
def add_activity(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    activity_type = request.form.get(
        "activity_type",
        ""
    ).strip().lower()

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip() or None

    activity_date_raw = request.form.get(
        "activity_date",
        ""
    ).strip()

    valid_activity_types = {
        "call",
        "email",
        "meeting",
    }
    # =========================================================
# ADD CLIENT NOTE / REMARK
# =========================================================

@clients_bp.route(
    "/<int:client_id>/notes/add",
    methods=["POST"]
)
@login_required
def add_note(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    note_text = request.form.get(
        "note_text",
        ""
    ).strip()

    if not note_text:
        flash(
            "Note or remark cannot be empty.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    if len(note_text) > 5000:
        flash(
            "Note is too long. Maximum 5000 characters allowed.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    note = ClientNote(
        client_id=client.id,
        note_text=note_text,
        created_by_id=current_user.id,
    )

    db.session.add(note)

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to save the note.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    flash(
        "Note added successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#notes"
    )


# =========================================================
# DELETE CLIENT NOTE
# Only note creator can delete
# =========================================================

@clients_bp.route(
    "/<int:client_id>/notes/<int:note_id>/delete",
    methods=["POST"]
)
@login_required
def delete_note(client_id, note_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    note = db.get_or_404(
        ClientNote,
        note_id
    )

    if note.client_id != client.id:
        flash(
            "Invalid note record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    if note.created_by_id != current_user.id:
        flash(
            "You can only delete notes created by you.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    try:
        db.session.delete(note)
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the note.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#notes"
        )

    flash(
        "Note deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#notes"
    )
    # =========================================================
# ADD CLIENT TASK / FOLLOW-UP REMINDER
# =========================================================

@clients_bp.route(
    "/<int:client_id>/tasks/add",
    methods=["POST"]
)
@login_required
def add_task(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    title = request.form.get(
        "title",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip() or None

    task_type = request.form.get(
        "task_type",
        ""
    ).strip().lower()

    due_date_raw = request.form.get(
        "due_date",
        ""
    ).strip()

    assigned_to_id = request.form.get(
        "assigned_to_id",
        type=int
    )

    priority = request.form.get(
        "priority",
        "medium"
    ).strip().lower()

    valid_task_types = {
        "follow_up",
        "call",
        "email",
        "meeting",
        "general",
    }

    valid_priorities = {
        "low",
        "medium",
        "high",
        "urgent",
    }

    # -----------------------------------------
    # VALIDATION
    # -----------------------------------------

    if not title:
        flash(
            "Task title is required.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    if task_type not in valid_task_types:
        flash(
            "Please select a valid task type.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    if priority not in valid_priorities:
        flash(
            "Please select a valid priority.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    if not due_date_raw:
        flash(
            "Due date and time are required.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    try:
        due_date = datetime.strptime(
            due_date_raw,
            "%Y-%m-%dT%H:%M"
        )

    except ValueError:
        flash(
            "Invalid due date or time.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    assigned_user = db.session.get(
        User,
        assigned_to_id
    )

    if (
        not assigned_user
        or not assigned_user.is_active_user
    ):
        flash(
            "Please select a valid active assignee.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    # -----------------------------------------
    # CREATE TASK
    # -----------------------------------------

    task = ClientTask(
        client_id=client.id,
        title=title,
        description=description,
        task_type=task_type,
        due_date=due_date,
        assigned_to_id=assigned_user.id,
        priority=priority,
        status="pending",
        created_by_id=current_user.id,
    )

    db.session.add(task)

    # -----------------------------------------
    # AUTO UPDATE NEXT FOLLOW-UP DATE
    # Only active follow-up style tasks
    # -----------------------------------------

    if task_type in {
        "follow_up",
        "call",
        "email",
        "meeting",
    }:
        task_follow_up_date = due_date.date()

        if (
            client.next_follow_up_date is None
            or task_follow_up_date
            < client.next_follow_up_date
        ):
            client.next_follow_up_date = (
                task_follow_up_date
            )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to create the task.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    flash(
        "Follow-up task created successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#tasks"
    )
    # =========================================================
# UPDATE CLIENT TASK STATUS
# =========================================================

@clients_bp.route(
    "/<int:client_id>/tasks/<int:task_id>/status",
    methods=["POST"]
)
@login_required
def update_task_status(client_id, task_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    task = db.get_or_404(
        ClientTask,
        task_id
    )

    if task.client_id != client.id:
        flash(
            "Invalid task record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    new_status = request.form.get(
        "status",
        ""
    ).strip().lower()

    valid_statuses = {
        "pending",
        "in_progress",
        "completed",
        "cancelled",
    }

    if new_status not in valid_statuses:
        flash(
            "Invalid task status selected.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    task.status = new_status

    if new_status == "completed":
        task.completed_at = datetime.now(
            timezone.utc
        )
    else:
        task.completed_at = None

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to update task status.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    flash(
        "Task status updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#tasks"
    )

    # =========================================================
# UPLOAD CLIENT DOCUMENTS FROM PROFILE
# =========================================================

@clients_bp.route(
    "/<int:client_id>/documents/upload",
    methods=["POST"]
)
@login_required
def upload_documents(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    uploaded_files = request.files.getlist(
        "attachments"
    )

    valid_files = [
        file
        for file in uploaded_files
        if file and file.filename
    ]

    if not valid_files:
        flash(
            "Please select at least one file.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#documents"
        )

    # Validate all files BEFORE saving any file
    for uploaded_file in valid_files:

        if not allowed_file(
            uploaded_file.filename
        ):
            flash(
                "Only PDF, JPG, JPEG and DOCX files are allowed.",
                "danger"
            )

            return redirect(
                url_for(
                    "clients.view_client",
                    client_id=client.id
                )
                + "#documents"
            )

    upload_folder = get_upload_folder()

    saved_paths = []

    try:
        for uploaded_file in valid_files:

            original_filename = secure_filename(
                uploaded_file.filename
            )

            extension = (
                original_filename
                .rsplit(".", 1)[1]
                .lower()
            )

            stored_filename = (
                f"{uuid.uuid4().hex}.{extension}"
            )

            absolute_path = os.path.join(
                upload_folder,
                stored_filename
            )

            uploaded_file.save(
                absolute_path
            )

            saved_paths.append(
                absolute_path
            )

            relative_path = os.path.join(
                "uploads",
                "clients",
                stored_filename
            ).replace("\\", "/")

            attachment = ClientAttachment(
                client_id=client.id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=relative_path,
                file_type=extension,
                uploaded_by_id=current_user.id,
            )

            db.session.add(
                attachment
            )

        db.session.commit()

    except Exception:
        db.session.rollback()

        # Remove files saved on disk if DB fails
        for saved_path in saved_paths:
            try:
                if os.path.exists(saved_path):
                    os.remove(saved_path)
            except OSError:
                pass

        flash(
            "Unable to upload the document.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#documents"
        )

    flash(
        f"{len(valid_files)} document(s) uploaded successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#documents"
    )


# =========================================================
# DOWNLOAD CLIENT DOCUMENT
# =========================================================

@clients_bp.route(
    "/<int:client_id>/documents/<int:attachment_id>/download"
)
@login_required
def download_document(
    client_id,
    attachment_id
):

    client = db.get_or_404(
        Client,
        client_id
    )

    attachment = db.get_or_404(
        ClientAttachment,
        attachment_id
    )

    if attachment.client_id != client.id:
        abort(404)

    upload_folder = get_upload_folder()

    return send_from_directory(
        upload_folder,
        attachment.stored_filename,
        as_attachment=True,
        download_name=attachment.original_filename
    )


# =========================================================
# DELETE CLIENT DOCUMENT
# =========================================================

@clients_bp.route(
    "/<int:client_id>/documents/<int:attachment_id>/delete",
    methods=["POST"]
)
@login_required
def delete_document(
    client_id,
    attachment_id
):

    client = db.get_or_404(
        Client,
        client_id
    )

    attachment = db.get_or_404(
        ClientAttachment,
        attachment_id
    )

    if attachment.client_id != client.id:
        abort(404)

    # Only uploader can delete
    if (
        attachment.uploaded_by_id
        != current_user.id
    ):
        flash(
            "You can only delete documents uploaded by you.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#documents"
        )

    absolute_path = os.path.join(
        current_app.root_path,
        "static",
        attachment.file_path
    )

    try:
        db.session.delete(
            attachment
        )

        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the document.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#documents"
        )

    # Delete physical file only after DB commit
    try:
        if os.path.exists(
            absolute_path
        ):
            os.remove(
                absolute_path
            )

    except OSError:
        pass

    flash(
        "Document deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#documents"
    )

    # =========================================================
# DELETE CLIENT TASK / FOLLOW-UP
# Permanent audit trail included
# =========================================================

@clients_bp.route(
    "/<int:client_id>/tasks/<int:task_id>/delete",
    methods=["POST"]
)
@login_required
def delete_task(client_id, task_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    task = db.get_or_404(
        ClientTask,
        task_id
    )

    # -----------------------------------------
    # SECURITY: TASK MUST BELONG TO CLIENT
    # -----------------------------------------

    if task.client_id != client.id:
        flash(
            "Invalid task record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    # -----------------------------------------
    # DELETE PERMISSION
    # Creator OR assigned user
    # -----------------------------------------

    if (
        task.created_by_id != current_user.id
        and task.assigned_to_id != current_user.id
    ):
        flash(
            "You do not have permission to delete this task.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    try:

        # -------------------------------------
        # PERMANENT AUDIT TRAIL
        # Save BEFORE deleting task
        # -------------------------------------

        log_client_audit(
            client_id=client.id,
            action_type="task",
            action="deleted",
            title="Follow-up task deleted",
            description=(
                f"Task: {task.title}\n"
                f"Type: {task.task_type_label}\n"
                f"Priority: {task.priority_label}\n"
                f"Status: {task.status_label}"
            )
        )

        # -------------------------------------
        # DELETE ORIGINAL TASK
        # -------------------------------------

        db.session.delete(task)

        # Push delete to current transaction.
        # Audit row is still pending in same transaction.
        db.session.flush()

        # -------------------------------------
        # RECALCULATE NEXT FOLLOW-UP DATE
        # -------------------------------------

        remaining_task = (
            db.session.execute(
                db.select(ClientTask)
                .where(
                    ClientTask.client_id == client.id,
                    ClientTask.status.in_(
                        [
                            "pending",
                            "in_progress",
                        ]
                    ),
                    ClientTask.task_type.in_(
                        [
                            "follow_up",
                            "call",
                            "email",
                            "meeting",
                        ]
                    )
                )
                .order_by(
                    ClientTask.due_date.asc()
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

        if remaining_task:
            client.next_follow_up_date = (
                remaining_task.due_date.date()
            )
        else:
            client.next_follow_up_date = None

        # Task delete + audit row save together
        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "DELETE TASK ERROR:",
            repr(error)
        )

        flash(
            "Unable to delete the task.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    flash(
        "Task deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#tasks"
    )

    # -----------------------------------------
    # DELETE PERMISSION
    # Creator OR assigned user
    # -----------------------------------------

    if (
        task.created_by_id != current_user.id
        and task.assigned_to_id != current_user.id
    ):
        flash(
            "You do not have permission to delete this task.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )
            # -------------------------------------
        # PERMANENT AUDIT TRAIL
        # Save details BEFORE task deletion
        # -------------------------------------

        log_client_audit(
            client_id=client.id,
            action_type="task",
            action="deleted",
            title="Follow-up task deleted",
            description=(
                f"Task: {task.title}\n"
                f"Type: {task.task_type_label}\n"
                f"Priority: {task.priority_label}\n"
                f"Status: {task.status_label}"
            )
        )
    try:
        db.session.delete(task)
        db.session.flush()

        # -------------------------------------
        # RECALCULATE NEXT FOLLOW-UP DATE
        # from remaining active follow-up tasks
        # -------------------------------------

        remaining_tasks = (
            db.session.execute(
                db.select(ClientTask)
                .where(
                    ClientTask.client_id == client.id,
                    ClientTask.status.in_(
                        [
                            "pending",
                            "in_progress",
                        ]
                    ),
                    ClientTask.task_type.in_(
                        [
                            "follow_up",
                            "call",
                            "email",
                            "meeting",
                        ]
                    )
                )
                .order_by(
                    ClientTask.due_date.asc()
                )
            )
            .scalars()
            .all()
        )

        if remaining_tasks:
            client.next_follow_up_date = (
                remaining_tasks[0]
                .due_date
                .date()
            )
        else:
            client.next_follow_up_date = None

        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to delete the task.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#tasks"
        )

    flash(
        "Task deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#tasks"
    )
    # -----------------------------------------
    # VALIDATION
    # -----------------------------------------

    if activity_type not in valid_activity_types:
        flash(
            "Please select a valid activity type.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#activities"
        )

    if not subject:
        flash(
            "Activity subject is required.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#activities"
        )

    # -----------------------------------------
    # PARSE ACTIVITY DATE + TIME
    # HTML datetime-local format:
    # 2026-07-06T16:30
    # -----------------------------------------

    if activity_date_raw:
        try:
            activity_date = datetime.strptime(
                activity_date_raw,
                "%Y-%m-%dT%H:%M"
            )

        except ValueError:
            flash(
                "Invalid activity date or time.",
                "danger"
            )

            return redirect(
                url_for(
                    "clients.view_client",
                    client_id=client.id
                )
                + "#activities"
            )

    else:
        activity_date = datetime.now(
            timezone.utc
        )

    # -----------------------------------------
    # CREATE ACTIVITY
    # -----------------------------------------

    activity = ClientActivity(
        client_id=client.id,
        activity_type=activity_type,
        subject=subject,
        description=description,
        activity_date=activity_date,
        created_by_id=current_user.id,
    )

    db.session.add(activity)

    # -----------------------------------------
    # AUTO UPDATE LAST CONTACT DATE
    # Document requirement
    # -----------------------------------------

    activity_contact_date = (
        activity_date.date()
    )

    if (
        client.last_contact_date is None
        or activity_contact_date
        >= client.last_contact_date
    ):
        client.last_contact_date = (
            activity_contact_date
        )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Unable to save the activity.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
            + "#activities"
        )

    flash(
        f"{activity.activity_type_label} "
        f"activity logged successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
        + "#activities"
    )
# =========================================================
# VIEW CLIENT
# =========================================================

@clients_bp.route("/<int:client_id>")
@login_required
def view_client(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )
    active_users = (
    db.session.execute(
        db.select(User)
        .where(User.is_active_user.is_(True))
        .order_by(User.full_name.asc())
    )
    .scalars()
    .all()
)
        # =====================================================
    # COMBINED CLIENT HISTORY / AUDIT TIMELINE
    # =====================================================

    client_history = []

    # -----------------------------------------
    # ACTIVITIES
    # -----------------------------------------

    for activity in client.activities:

        client_history.append({
            "type": "activity",
            "date": activity.activity_date,
            "title": activity.subject,
            "description": activity.description,
            "actor": (
                activity.created_by.full_name
                if activity.created_by
                else "Unknown User"
            ),
            "meta": activity.activity_type_label,
            "icon": {
                "call": "telephone-fill",
                "email": "envelope-fill",
                "meeting": "people-fill",
            }.get(
                activity.activity_type,
                "activity"
            ),
        })

    # -----------------------------------------
    # STATUS CHANGES
    # -----------------------------------------

    for history in client.status_history:

        old_label = (
            history.old_status
            .replace("_", " ")
            .title()
            if history.old_status
            else "No Status"
        )

        new_label = (
            history.new_status
            .replace("_", " ")
            .title()
        )

        client_history.append({
            "type": "status",
            "date": history.changed_at,
            "title": (
                f"Status changed: "
                f"{old_label} → {new_label}"
            ),
            "description": history.remarks,
            "actor": (
                history.changed_by.full_name
                if history.changed_by
                else "Unknown User"
            ),
            "meta": "Status Change",
            "icon": "arrow-left-right",
        })

    # -----------------------------------------
    # NOTES
    # -----------------------------------------

    for note in client.client_notes:

        client_history.append({
            "type": "note",
            "date": note.created_at,
            "title": "Internal note added",
            "description": note.note_text,
            "actor": (
                note.created_by.full_name
                if note.created_by
                else "Unknown User"
            ),
            "meta": "Note / Remark",
            "icon": "chat-left-text-fill",
        })

    # -----------------------------------------
    # TASKS / FOLLOW-UPS
    # -----------------------------------------

    for task in client.tasks:

        client_history.append({
            "type": "task",
            "date": task.created_at,
            "title": task.title,
            "description": task.description,
            "actor": (
                task.created_by.full_name
                if task.created_by
                else "Unknown User"
            ),
            "meta": (
                f"{task.task_type_label} • "
                f"{task.status_label}"
            ),
            "icon": "calendar2-check-fill",
        })

    # -----------------------------------------
    # DOCUMENTS
    # -----------------------------------------

    for attachment in client.attachments:

        client_history.append({
            "type": "document",
            "date": attachment.uploaded_at,
            "title": attachment.original_filename,
            "description": (
                f"{attachment.file_type.upper()} "
                f"document uploaded"
            ),
            "actor": (
                attachment.uploaded_by.full_name
                if attachment.uploaded_by
                else "Unknown User"
            ),
            "meta": "Document Upload",
            "icon": "file-earmark-arrow-up-fill",
        })

    # -----------------------------------------
    # NEWEST FIRST
    # -----------------------------------------

    client_history.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    return render_template(
    "clients/view.html",
    client=client,
    client_history=client_history,
    statuses=CLIENT_STATUSES,
    services=dict(SERVICE_OPTIONS),
    categories=dict(CLIENT_CATEGORIES),
    lead_sources=dict(LEAD_SOURCES),
    activity_types=[
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
    ],
    task_assignees=active_users,
task_types=[
    ("follow_up", "Follow-Up"),
    ("call", "Call"),
    ("email", "Email"),
    ("meeting", "Meeting"),
    ("general", "General Task"),
],
task_priorities=[
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("urgent", "Urgent"),
],
)
# =========================================================
# EDIT CLIENT
# =========================================================

@clients_bp.route(
    "/<int:client_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_client(client_id):

    client = db.get_or_404(Client, client_id)
    options = get_form_options()

    if request.method == "POST":

        company_name = request.form.get(
            "company_name", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        new_status = request.form.get(
            "status", ""
        ).strip()

        contact_person_name = request.form.get(
            "contact_person_name", ""
        ).strip()

        primary_phone = request.form.get(
            "primary_phone", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        address_line_1 = request.form.get(
            "address_line_1", ""
        ).strip()

        assigned_to_id = request.form.get(
            "assigned_to_id",
            type=int
        )

        services_needed = request.form.getlist(
            "services_needed"
        )

        required_values = [
            company_name,
            category,
            new_status,
            contact_person_name,
            primary_phone,
            email,
            address_line_1,
            assigned_to_id,
        ]

        if not all(required_values):
            flash(
                "Please complete all required fields.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        valid_categories = {
            value
            for value, label in CLIENT_CATEGORIES
        }

        valid_statuses = {
            value
            for value, label in CLIENT_STATUSES
        }

        valid_services = {
            value
            for value, label in SERVICE_OPTIONS
        }

        valid_priorities = {
            value
            for value, label in PRIORITY_LEVELS
        }

        valid_lead_sources = {
            value
            for value, label in LEAD_SOURCES
        }

        if category not in valid_categories:
            flash(
                "Invalid client category selected.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        if new_status not in valid_statuses:
            flash(
                "Invalid client status selected.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        services_needed = [
            service
            for service in services_needed
            if service in valid_services
        ]

        if not services_needed:
            flash(
                "Select at least one required service.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        assigned_owner = db.session.get(
            User,
            assigned_to_id
        )

        if (
            not assigned_owner
            or not assigned_owner.is_active_user
        ):
            flash(
                "Please select a valid active owner.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        priority_level = request.form.get(
            "priority_level", ""
        ).strip() or None

        if (
            priority_level
            and priority_level not in valid_priorities
        ):
            priority_level = None

        lead_source = request.form.get(
            "lead_source", ""
        ).strip() or None

        if (
            lead_source
            and lead_source not in valid_lead_sources
        ):
            lead_source = None

        raw_tags = request.form.get(
            "tags", ""
        )

        tags = []

        if raw_tags:
            tags = [
                tag.strip()
                for tag in raw_tags.split(",")
                if tag.strip()
            ]

            tags = list(dict.fromkeys(tags))

        old_status = client.status

        client.company_name = company_name
        client.category = category
        client.status = new_status

        client.contact_person_name = (
            contact_person_name
        )

        client.designation = (
            request.form.get(
                "designation", ""
            ).strip() or None
        )

        client.primary_phone = primary_phone

        client.secondary_phone = (
            request.form.get(
                "secondary_phone", ""
            ).strip() or None
        )

        client.email = email

        client.website_url = (
            request.form.get(
                "website_url", ""
            ).strip() or None
        )

        client.address_line_1 = address_line_1

        client.address_line_2 = (
            request.form.get(
                "address_line_2", ""
            ).strip() or None
        )

        client.industry_sector = (
            request.form.get(
                "industry_sector", ""
            ).strip() or None
        )

        client.services_needed = services_needed
        client.assigned_to_id = assigned_to_id
        client.lead_source = lead_source

        client.last_contact_date = parse_date(
            request.form.get(
                "last_contact_date"
            )
        )

        client.next_follow_up_date = parse_date(
            request.form.get(
                "next_follow_up_date"
            )
        )

        client.priority_level = priority_level

        client.notes = (
            request.form.get(
                "notes", ""
            ).strip() or None
        )

        client.tags = tags

        # -----------------------------------------
        # STATUS HISTORY
        # -----------------------------------------

        if old_status != new_status:

            status_remarks = (
                request.form.get(
                    "status_remarks", ""
                ).strip()
                or "Status changed during client edit."
            )

            history = ClientStatusHistory(
                client_id=client.id,
                old_status=old_status,
                new_status=new_status,
                changed_by_id=current_user.id,
                remarks=status_remarks,
            )

            db.session.add(history)

        # -----------------------------------------
        # NEW ATTACHMENTS
        # -----------------------------------------

        uploaded_files = request.files.getlist(
            "attachments"
        )

        upload_folder = get_upload_folder()

        for uploaded_file in uploaded_files:

            if (
                not uploaded_file
                or not uploaded_file.filename
            ):
                continue

            if not allowed_file(
                uploaded_file.filename
            ):
                db.session.rollback()

                flash(
                    "Only PDF, JPG, JPEG and DOCX "
                    "attachments are allowed.",
                    "danger"
                )

                return render_template(
                    "clients/edit.html",
                    client=client,
                    **options
                )

            original_filename = secure_filename(
                uploaded_file.filename
            )

            extension = (
                original_filename
                .rsplit(".", 1)[1]
                .lower()
            )

            stored_filename = (
                f"{uuid.uuid4().hex}.{extension}"
            )

            absolute_path = os.path.join(
                upload_folder,
                stored_filename
            )

            uploaded_file.save(absolute_path)

            relative_path = os.path.join(
                "uploads",
                "clients",
                stored_filename
            ).replace("\\", "/")

            attachment = ClientAttachment(
                client_id=client.id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=relative_path,
                file_type=extension,
                uploaded_by_id=current_user.id,
            )

            db.session.add(attachment)

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update the client record.",
                "danger"
            )

            return render_template(
                "clients/edit.html",
                client=client,
                **options
            )

        flash(
            f"{client.company_name} updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    return render_template(
        "clients/edit.html",
        client=client,
        **options
    )

# =========================================================
# ARCHIVE CLIENT
# =========================================================

@clients_bp.route(
    "/<int:client_id>/archive",
    methods=["POST"]
)
@login_required
def archive_client(client_id):

    client = db.get_or_404(
        Client,
        client_id
    )

    client.is_archived = True

    db.session.commit()

    flash(
        f"{client.company_name} was archived.",
        "success"
    )

    return redirect(
        url_for(
            "clients.client_list"
        )
    )
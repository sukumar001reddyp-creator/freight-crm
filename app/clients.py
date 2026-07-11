import os
from io import BytesIO
import io
import re
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
    send_file,
    send_from_directory,
    
)

from flask_login import (
    login_required,
    current_user,
)

from werkzeug.utils import secure_filename

from sqlalchemy import or_

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from app import db

from app.models import (
    Client,
    ClientActivity,
    ClientAttachment,
    ClientAuditLog,
    ClientNote,
    ClientStatusHistory,
    ClientPipelineHistory,
    ClientTask,
    User,
    Enquiry,
    Quotation,
    Shipment,
    ClientPortalUser,
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


PIPELINE_STAGES = [
    ("prospect", "Prospect"),
    ("qualified", "Qualified"),
    ("needs_analysis", "Needs Analysis"),
    ("proposal", "Proposal / Quotation"),
    ("negotiation", "Negotiation"),
    ("won", "Won"),
    ("lost", "Lost"),
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
    if is_sales_user():
        owners = [current_user]
    else:
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


def is_admin_user():
    return getattr(current_user, "role", None) == "admin"


def is_sales_user():
    return getattr(current_user, "role", None) in {
        "sales",
        "sales_executive",
    }


def can_access_client(client):
    """
    Admin: all clients.
    Sales Executive: only clients assigned to that user.
    Other roles are left unchanged here for future role modules.
    """
    if is_admin_user():
        return True

    if is_sales_user():
        return client.assigned_to_id == current_user.id

    return True


def get_accessible_client_or_404(client_id):
    """
    Prevent direct-URL access to another salesperson's client.
    Returns 404 instead of exposing that the record exists.
    """
    client = db.get_or_404(Client, client_id)

    if not can_access_client(client):
        abort(404)

    return client



# =========================================================
# CLIENT EXPORT HELPERS
# PDF + EXCEL
# =========================================================

def export_safe_filename(value):
    value = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        (value or "client").strip()
    )

    value = value.strip("._")

    return value[:80] or "client"


def export_text(value):
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return ", ".join(
            export_text(item)
            for item in value
        )

    return str(value)


def export_date(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime(
            "%Y-%m-%d %H:%M"
        )

    try:
        return value.strftime(
            "%Y-%m-%d"
        )
    except AttributeError:
        return export_text(value)


def export_label(value, options=None):
    if value is None:
        return ""

    if options:
        return dict(options).get(
            value,
            export_text(value)
            .replace("_", " ")
            .title()
        )

    return (
        export_text(value)
        .replace("_", " ")
        .title()
    )


def get_client_export_data(client):
    """
    Build one shared export dataset so PDF and Excel
    contain the same CRM information.
    """

    owner = db.session.get(
        User,
        client.assigned_to_id
    )

    creator = db.session.get(
        User,
        client.created_by_id
    )

    activities = (
        db.session.execute(
            db.select(ClientActivity)
            .where(
                ClientActivity.client_id == client.id
            )
            .order_by(
                ClientActivity.activity_date.desc(),
                ClientActivity.id.desc()
            )
        )
        .scalars()
        .all()
    )

    notes = (
        db.session.execute(
            db.select(ClientNote)
            .where(
                ClientNote.client_id == client.id
            )
            .order_by(
                ClientNote.created_at.desc(),
                ClientNote.id.desc()
            )
        )
        .scalars()
        .all()
    )

    tasks = (
        db.session.execute(
            db.select(ClientTask)
            .where(
                ClientTask.client_id == client.id
            )
            .order_by(
                ClientTask.due_date.desc(),
                ClientTask.id.desc()
            )
        )
        .scalars()
        .all()
    )

    documents = (
        db.session.execute(
            db.select(ClientAttachment)
            .where(
                ClientAttachment.client_id == client.id
            )
            .order_by(
                ClientAttachment.uploaded_at.desc(),
                ClientAttachment.id.desc()
            )
        )
        .scalars()
        .all()
    )

    status_history = (
        db.session.execute(
            db.select(ClientStatusHistory)
            .where(
                ClientStatusHistory.client_id == client.id
            )
            .order_by(
                ClientStatusHistory.changed_at.desc(),
                ClientStatusHistory.id.desc()
            )
        )
        .scalars()
        .all()
    )

    pipeline_history = (
        db.session.execute(
            db.select(ClientPipelineHistory)
            .where(
                ClientPipelineHistory.client_id == client.id
            )
            .order_by(
                ClientPipelineHistory.moved_at.desc(),
                ClientPipelineHistory.id.desc()
            )
        )
        .scalars()
        .all()
    )

    audit_logs = (
        db.session.execute(
            db.select(ClientAuditLog)
            .where(
                ClientAuditLog.client_id == client.id
            )
            .order_by(
                ClientAuditLog.created_at.desc(),
                ClientAuditLog.id.desc()
            )
        )
        .scalars()
        .all()
    )

    enquiries = (
        db.session.execute(
            db.select(Enquiry)
            .where(
                Enquiry.client_id == client.id
            )
            .order_by(
                Enquiry.id.desc()
            )
        )
        .scalars()
        .all()
    )

    quotations = (
        db.session.execute(
            db.select(Quotation)
            .join(
                Enquiry,
                Quotation.enquiry_id == Enquiry.id
            )
            .where(
                Enquiry.client_id == client.id
            )
            .order_by(
                Quotation.id.desc()
            )
        )
        .scalars()
        .all()
    )

    shipments = (
        db.session.execute(
            db.select(Shipment)
            .where(
                Shipment.client_id == client.id
            )
            .order_by(
                Shipment.id.desc()
            )
        )
        .scalars()
        .all()
    )

    profile = [
        ("Client ID", client.id),
        ("Client Reference", client.client_reference),
        ("Company Name", client.company_name),
        (
            "Category",
            export_label(
                client.category,
                CLIENT_CATEGORIES
            )
        ),
        (
            "Status",
            export_label(
                client.status,
                CLIENT_STATUSES
            )
        ),
        (
            "Pipeline Stage",
            export_label(
                client.pipeline_stage,
                PIPELINE_STAGES
            )
        ),
        (
            "Contact Person",
            client.contact_person_name
        ),
        ("Designation", client.designation),
        ("Primary Phone", client.primary_phone),
        ("Secondary Phone", client.secondary_phone),
        ("Email", client.email),
        ("Website", client.website_url),
        ("Address Line 1", client.address_line_1),
        ("Address Line 2", client.address_line_2),
        ("Industry / Sector", client.industry_sector),
        (
            "Services Needed",
            [
                dict(SERVICE_OPTIONS).get(
                    item,
                    export_label(item)
                )
                for item in (
                    client.services_needed or []
                )
            ]
        ),
        (
            "Assigned Owner",
            owner.full_name
            if owner
            else "Unassigned"
        ),
        (
            "Lead Source",
            export_label(
                client.lead_source,
                LEAD_SOURCES
            )
        ),
        (
            "Priority",
            export_label(
                client.priority_level,
                PRIORITY_LEVELS
            )
        ),
        (
            "Last Contact Date",
            export_date(
                client.last_contact_date
            )
        ),
        (
            "Next Follow-Up Date",
            export_date(
                client.next_follow_up_date
            )
        ),
        ("Tags", client.tags or []),
        ("Profile Notes", client.notes),
        (
            "Created By",
            creator.full_name
            if creator
            else ""
        ),
        (
            "Date Added",
            export_date(
                getattr(
                    client,
                    "date_added",
                    None
                )
            )
        ),
        (
            "Archived",
            "Yes"
            if client.is_archived
            else "No"
        ),
    ]

    return {
        "profile": profile,
        "activities": activities,
        "notes": notes,
        "tasks": tasks,
        "documents": documents,
        "status_history": status_history,
        "pipeline_history": pipeline_history,
        "audit_logs": audit_logs,
        "enquiries": enquiries,
        "quotations": quotations,
        "shipments": shipments,
    }


def pdf_paragraph(value, style):
    safe_value = (
        export_text(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )

    return Paragraph(
        safe_value or "—",
        style
    )


def pdf_table(
    rows,
    widths,
    body_style,
    header=True
):
    prepared = []

    for row in rows:
        prepared.append([
            pdf_paragraph(
                value,
                body_style
            )
            for value in row
        ])

    table = Table(
        prepared,
        colWidths=widths,
        repeatRows=1 if header else 0,
        hAlign="LEFT"
    )

    commands = [
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.35,
            colors.HexColor("#CBD5E1")
        ),
        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "TOP"
        ),
        (
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            5
        ),
        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            5
        ),
        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            5
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            5
        ),
    ]

    if header:
        commands.extend([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0F172A")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
        ])

    table.setStyle(
        TableStyle(commands)
    )

    return table


def excel_prepare_sheet(
    ws,
    title,
    headers
):
    ws.title = title

    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(
            bold=True,
            color="FFFFFF"
        )
        cell.fill = PatternFill(
            "solid",
            fgColor="0F172A"
        )
        cell.alignment = Alignment(
            vertical="top"
        )

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = (
        f"A1:{get_column_letter(len(headers))}1"
    )


def excel_finish_sheet(ws):
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )

    for column_cells in ws.columns:
        letter = get_column_letter(
            column_cells[0].column
        )

        max_length = 0

        for cell in column_cells:
            value = export_text(cell.value)

            if value:
                max_length = max(
                    max_length,
                    min(len(value), 60)
                )

        ws.column_dimensions[letter].width = max(
            12,
            min(max_length + 2, 45)
        )


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

    pipeline_stage = request.args.get(
        "pipeline_stage",
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

    # Sales data isolation:
    # each salesperson sees only clients assigned to them.
    if is_sales_user():
        query = query.filter(
            Client.assigned_to_id == current_user.id
        )


    # -----------------------------------------
    # SEARCH
    # -----------------------------------------

    if search:
        search_term = f"%{search}%"

        query = query.filter(
            or_(
                Client.client_reference.ilike(
                    search_term
                ),
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

    if assigned_to and not is_sales_user():
        query = query.filter(
            Client.assigned_to_id == assigned_to
        )

    if priority:
        query = query.filter(
            Client.priority_level == priority
        )

    if pipeline_stage:
        query = query.filter(
            Client.pipeline_stage == pipeline_stage
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
            Client.next_follow_up_date.is_(None),
            Client.next_follow_up_date.asc(),
            Client.id.desc()
        )

    elif sort == "last_activity":
        query = query.order_by(
            Client.last_contact_date.is_(None),
            Client.last_contact_date.desc(),
            Client.id.desc()
        )

    else:
        query = query.order_by(
            Client.date_added.desc(),
            Client.id.desc()
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

    if is_sales_user():
        owners = [current_user]
    else:
        owners = (
            User.query
            .filter_by(is_active_user=True)
            .order_by(User.full_name.asc())
            .all()
        )


    # -----------------------------------------
    # STATS
    # -----------------------------------------

    stats_query = Client.query.filter(
        Client.is_archived.is_(False)
    )

    if is_sales_user():
        stats_query = stats_query.filter(
            Client.assigned_to_id == current_user.id
        )

    total_clients = stats_query.count()

    active_clients = stats_query.filter(
        Client.status.in_([
            "active",
            "key",
            "reactivated",
        ])
    ).count()

    lead_clients = stats_query.filter(
        Client.status.in_([
            "lead",
            "new",
        ])
    ).count()

    at_risk_clients = stats_query.filter(
        Client.status == "at_risk"
    ).count()

    return render_template(
        "clients/list.html",
        clients=clients,
        pagination=pagination,
        total_clients=total_clients,
        active_clients=active_clients,
        lead_clients=lead_clients,
        at_risk_clients=at_risk_clients,
        statuses=CLIENT_STATUSES,
        services=SERVICE_OPTIONS,
        categories=CLIENT_CATEGORIES,
        priorities=PRIORITY_LEVELS,
        owners=owners,
        pipeline_stages=PIPELINE_STAGES,
        selected_search=search,
        selected_category=category,
        selected_status=status,
        selected_assigned_to=assigned_to,
        selected_priority=priority,
        selected_pipeline_stage=pipeline_stage,
        selected_sort=sort,
    )



# =========================================================
# BULK REASSIGN CLIENT OWNER
# Admin only
# =========================================================

@clients_bp.route(
    "/bulk/reassign-owner",
    methods=["POST"]
)
@login_required
def bulk_reassign_owner():

    if not is_admin_user():
        flash(
            "Only Admin users can bulk reassign client owners.",
            "danger"
        )
        return redirect(
            url_for("clients.client_list")
        )

    raw_client_ids = request.form.getlist(
        "client_ids"
    )

    new_owner_id = request.form.get(
        "new_owner_id",
        type=int
    )

    if not raw_client_ids:
        flash(
            "Select at least one client.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    if not new_owner_id:
        flash(
            "Select a new owner.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    try:
        client_ids = sorted({
            int(client_id)
            for client_id in raw_client_ids
            if str(client_id).isdigit()
        })
    except (TypeError, ValueError):
        client_ids = []

    if not client_ids:
        flash(
            "No valid clients were selected.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    new_owner = db.session.get(
        User,
        new_owner_id
    )

    if not new_owner or not new_owner.is_active_user:
        flash(
            "Selected owner is invalid or inactive.",
            "danger"
        )
        return redirect(
            url_for("clients.client_list")
        )

    clients = (
        Client.query
        .filter(
            Client.id.in_(client_ids),
            Client.is_archived.is_(False)
        )
        .order_by(Client.id.asc())
        .all()
    )

    if not clients:
        flash(
            "No active clients were available for reassignment.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    changed_count = 0

    try:
        for client in clients:

            old_owner = client.assigned_to

            if client.assigned_to_id == new_owner.id:
                continue

            old_owner_name = (
                old_owner.full_name
                if old_owner
                else "Unassigned"
            )

            client.assigned_to_id = new_owner.id

            log_client_audit(
                client_id=client.id,
                action_type="owner_assignment",
                action="reassigned",
                title="Client owner reassigned",
                description=(
                    f"From: {old_owner_name}\n"
                    f"To: {new_owner.full_name}\n"
                    f"Method: Bulk reassignment"
                )
            )

            changed_count += 1

        db.session.commit()

        if changed_count:
            flash(
                f"{changed_count} client(s) reassigned to "
                f"{new_owner.full_name}.",
                "success"
            )
        else:
            flash(
                "Selected clients are already assigned to that owner.",
                "info"
            )

    except Exception as error:
        db.session.rollback()

        print(
            "BULK REASSIGN OWNER ERROR:",
            repr(error)
        )

        flash(
            "Unable to complete bulk owner reassignment.",
            "danger"
        )

    return redirect(
        url_for("clients.client_list")
    )



# =========================================================
# BULK EXPORT SELECTED CLIENTS TO EXCEL
# Admin only
# =========================================================

@clients_bp.route(
    "/bulk/export/excel",
    methods=["POST"]
)
@login_required
def bulk_export_clients_excel():

    if not is_admin_user():
        flash(
            "Only Admin users can bulk export clients.",
            "danger"
        )
        return redirect(
            url_for("clients.client_list")
        )

    raw_client_ids = request.form.getlist(
        "client_ids"
    )

    try:
        client_ids = sorted({
            int(client_id)
            for client_id in raw_client_ids
            if str(client_id).isdigit()
        })
    except (TypeError, ValueError):
        client_ids = []

    if not client_ids:
        flash(
            "Select at least one client to export.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    clients = (
        Client.query
        .filter(
            Client.id.in_(client_ids),
            Client.is_archived.is_(False)
        )
        .order_by(Client.company_name.asc())
        .all()
    )

    if not clients:
        flash(
            "No active clients were available for export.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Selected Clients"

    headers = [
        "Client Reference",
        "Company Name",
        "Contact Person",
        "Email",
        "Primary Phone",
        "Secondary Phone",
        "Category",
        "Status",
        "Pipeline Stage",
        "Priority",
        "Owner",
        "Industry",
        "Next Follow-Up",
        "Last Contact",
        "Date Added",
    ]

    sheet.append(headers)

    for client in clients:
        sheet.append([
            client.client_reference or "",
            client.company_name or "",
            client.contact_person_name or "",
            client.email or "",
            client.primary_phone or "",
            client.secondary_phone or "",
            client.category or "",
            client.status or "",
            client.pipeline_stage or "",
            client.priority_level or "",
            (
                client.assigned_to.full_name
                if client.assigned_to
                else ""
            ),
            client.industry_sector or "",
            
            (
                client.next_follow_up_date.strftime(
                    "%Y-%m-%d"
                )
                if client.next_follow_up_date
                else ""
            ),
            (
                client.last_contact_date.strftime(
                    "%Y-%m-%d"
                )
                if client.last_contact_date
                else ""
            ),
            (
                client.date_added.strftime(
                    "%Y-%m-%d %H:%M"
                )
                if client.date_added
                else ""
            ),
        ])

    for cell in sheet[1]:
        cell.font = Font(
            bold=True,
            color="FFFFFF"
        )
        cell.fill = PatternFill(
            "solid",
            fgColor="C62828"
        )

    for column_cells in sheet.columns:
        max_length = 0

        for cell in column_cells:
            value = (
                ""
                if cell.value is None
                else str(cell.value)
            )
            max_length = max(
                max_length,
                len(value)
            )

        sheet.column_dimensions[
            get_column_letter(
                column_cells[0].column
            )
        ].width = min(
            max(max_length + 2, 12),
            35
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = (
        "selected_clients_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        ".xlsx"
    )

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )



# =========================================================
# BULK TAG SELECTED CLIENTS
# Admin only
# =========================================================

@clients_bp.route(
    "/bulk/tag",
    methods=["POST"]
)
@login_required
def bulk_tag_clients():

    if not is_admin_user():
        flash(
            "Only Admin users can bulk tag clients.",
            "danger"
        )
        return redirect(
            url_for("clients.client_list")
        )

    raw_client_ids = request.form.getlist("client_ids")
    tag_value = (request.form.get("tag_value") or "").strip()
    tag_action = (request.form.get("tag_action") or "add").strip().lower()

    try:
        client_ids = sorted({
            int(client_id)
            for client_id in raw_client_ids
            if str(client_id).isdigit()
        })
    except (TypeError, ValueError):
        client_ids = []

    if not client_ids:
        flash(
            "Select at least one client to tag.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    # Normalize whitespace and keep labels compact.
    tag_value = re.sub(r"\s+", " ", tag_value).strip()

    if not tag_value:
        flash(
            "Enter a tag / label.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    if len(tag_value) > 50:
        flash(
            "Tag must be 50 characters or fewer.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    if tag_action not in {"add", "remove"}:
        flash(
            "Invalid bulk tag action.",
            "danger"
        )
        return redirect(
            url_for("clients.client_list")
        )

    selected_clients = (
        Client.query
        .filter(
            Client.id.in_(client_ids),
            Client.is_archived.is_(False)
        )
        .order_by(Client.id.asc())
        .all()
    )

    if not selected_clients:
        flash(
            "No active clients were available for tagging.",
            "warning"
        )
        return redirect(
            url_for("clients.client_list")
        )

    changed_count = 0

    try:
        for client in selected_clients:
            current_tags = list(client.tags or [])

            # Case-insensitive duplicate matching while preserving display text.
            matching_tag = next(
                (
                    existing
                    for existing in current_tags
                    if str(existing).strip().casefold()
                    == tag_value.casefold()
                ),
                None
            )

            if tag_action == "add":
                if matching_tag is not None:
                    continue

                current_tags.append(tag_value)
                client.tags = current_tags

                log_client_audit(
                    client_id=client.id,
                    action_type="tags",
                    action="added",
                    title="Client tag added",
                    description=(
                        f"Tag: {tag_value}\n"
                        f"Method: Bulk tagging"
                    )
                )

                changed_count += 1

            else:
                if matching_tag is None:
                    continue

                client.tags = [
                    existing
                    for existing in current_tags
                    if str(existing).strip().casefold()
                    != tag_value.casefold()
                ]

                log_client_audit(
                    client_id=client.id,
                    action_type="tags",
                    action="removed",
                    title="Client tag removed",
                    description=(
                        f"Tag: {tag_value}\n"
                        f"Method: Bulk tagging"
                    )
                )

                changed_count += 1

        db.session.commit()

        if changed_count:
            verb = "added to" if tag_action == "add" else "removed from"
            flash(
                f'Tag "{tag_value}" {verb} '
                f"{changed_count} client(s).",
                "success"
            )
        else:
            flash(
                "No client tags needed changing.",
                "info"
            )

    except Exception as error:
        db.session.rollback()

        print(
            "BULK TAG ERROR:",
            repr(error)
        )

        flash(
            "Unable to complete bulk tagging.",
            "danger"
        )

    return redirect(
        url_for("clients.client_list")
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

        if is_sales_user():
            assigned_to_id = current_user.id
        else:
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

        client.client_reference = (
            f"CLI-{datetime.now(timezone.utc).year}-{client.id:06d}"
        )

        db.session.commit()


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
# CONVERT LEAD / PIPELINE CLIENT TO ACTIVE
# Section 5 dedicated action + permanent audit
# =========================================================

@clients_bp.route(
    "/<int:client_id>/convert-to-active",
    methods=["POST"]
)
@login_required
def convert_to_active(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    eligible_statuses = {
        "lead",
        "new",
    }

    eligible_categories = {
        "pipeline",
    }

    if (
        client.status not in eligible_statuses
        and client.category not in eligible_categories
    ):
        flash(
            "Only Lead, New or Pipeline records can be converted to Active.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    old_status = client.status
    old_category = client.category

    remarks = request.form.get(
        "remarks",
        ""
    ).strip() or "Converted to Active Client."

    try:
        client.status = "active"

        status_history = ClientStatusHistory(
            client_id=client.id,
            old_status=old_status,
            new_status="active",
            changed_by_id=current_user.id,
            remarks=remarks,
        )

        db.session.add(
            status_history
        )

        log_client_audit(
            client_id=client.id,
            action_type="client_conversion",
            action="converted_to_active",
            title="Client converted to Active",
            description=(
                f"Previous status: {old_status}\n"
                f"Category: {old_category}\n"
                f"Remarks: {remarks}"
            )
        )

        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "CONVERT CLIENT ERROR:",
            repr(error)
        )

        flash(
            "Unable to convert the client to Active.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    flash(
        f"{client.company_name} converted to Active Client successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
    )


# =========================================================
# ASSIGN / REASSIGN CLIENT OWNER
# Section 5 dedicated action + permanent audit
# =========================================================

@clients_bp.route(
    "/<int:client_id>/reassign-owner",
    methods=["POST"]
)
@login_required
def reassign_owner(client_id):

    if not is_admin_user():
        abort(403)

    client = get_accessible_client_or_404(
        client_id
    )

    new_owner_id = request.form.get(
        "assigned_to_id",
        type=int
    )

    remarks = request.form.get(
        "remarks",
        ""
    ).strip() or None

    new_owner = db.session.get(
        User,
        new_owner_id
    )

    if (
        not new_owner
        or not new_owner.is_active_user
    ):
        flash(
            "Please select a valid active owner.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    if client.assigned_to_id == new_owner.id:
        flash(
            "This user is already the assigned owner.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    old_owner = db.session.get(
        User,
        client.assigned_to_id
    )

    old_owner_name = (
        old_owner.full_name
        if old_owner
        else "Unassigned"
    )

    try:
        client.assigned_to_id = new_owner.id

        log_client_audit(
            client_id=client.id,
            action_type="owner_assignment",
            action="reassigned",
            title="Client owner reassigned",
            description=(
                f"From: {old_owner_name}\n"
                f"To: {new_owner.full_name}"
                + (
                    f"\nRemarks: {remarks}"
                    if remarks
                    else ""
                )
            )
        )

        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "REASSIGN OWNER ERROR:",
            repr(error)
        )

        flash(
            "Unable to reassign the client owner.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    flash(
        f"Client owner reassigned to {new_owner.full_name}.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
    )


# =========================================================
# MOVE CLIENT THROUGH PIPELINE / FUNNEL
# Section 5 dedicated action + movement history + audit
# =========================================================

@clients_bp.route(
    "/<int:client_id>/move-pipeline-stage",
    methods=["POST"]
)
@login_required
def move_pipeline_stage(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    new_stage = request.form.get(
        "pipeline_stage",
        ""
    ).strip()

    remarks = request.form.get(
        "remarks",
        ""
    ).strip() or None

    valid_stages = [
        value
        for value, label
        in PIPELINE_STAGES
    ]

    if new_stage not in valid_stages:
        flash(
            "Invalid pipeline stage selected.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    old_stage = client.pipeline_stage

    if old_stage == new_stage:
        flash(
            "Client is already in that pipeline stage.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    # Strict ordered movement:
    # - First assignment may start at Prospect only.
    # - Normal movement is one stage forward or backward.
    # - Won/Lost are terminal outcomes.
    stage_index = {
        stage: index
        for index, stage
        in enumerate(valid_stages)
    }

    terminal_stages = {
        "won",
        "lost",
    }

    if old_stage is None:
        if new_stage != "prospect":
            flash(
                "Pipeline must start at Prospect.",
                "warning"
            )

            return redirect(
                url_for(
                    "clients.view_client",
                    client_id=client.id
                )
            )

    elif old_stage in terminal_stages:
        flash(
            "Won or Lost is a terminal pipeline stage. "
            "It cannot be moved further.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    else:
        old_index = stage_index.get(old_stage)
        new_index = stage_index.get(new_stage)

        if old_index is None:
            flash(
                "Current pipeline stage is invalid. "
                "Please correct the record before moving it.",
                "danger"
            )

            return redirect(
                url_for(
                    "clients.view_client",
                    client_id=client.id
                )
            )

        allowed_indexes = {
            old_index - 1,
            old_index + 1,
        }

        if new_index not in allowed_indexes:
            flash(
                "Pipeline stages must move one step at a time.",
                "warning"
            )

            return redirect(
                url_for(
                    "clients.view_client",
                    client_id=client.id
                )
            )

    old_label = (
        dict(PIPELINE_STAGES).get(
            old_stage,
            "Not Started"
        )
    )

    new_label = dict(PIPELINE_STAGES)[
        new_stage
    ]

    try:
        client.pipeline_stage = new_stage

        movement = ClientPipelineHistory(
            client_id=client.id,
            old_stage=old_stage,
            new_stage=new_stage,
            remarks=remarks,
            moved_by_id=current_user.id,
        )

        db.session.add(
            movement
        )

        log_client_audit(
            client_id=client.id,
            action_type="pipeline",
            action="stage_moved",
            title="Pipeline stage moved",
            description=(
                f"From: {old_label}\n"
                f"To: {new_label}"
                + (
                    f"\nRemarks: {remarks}"
                    if remarks
                    else ""
                )
            )
        )

        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "MOVE PIPELINE STAGE ERROR:",
            repr(error)
        )

        flash(
            "Unable to move the pipeline stage.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    flash(
        f"Pipeline moved to {new_label} successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
    )


# =========================================================
# CHANGE CLIENT STATUS
# =========================================================

@clients_bp.route(
    "/<int:client_id>/change-status",
    methods=["POST"]
)
@login_required
def change_status(client_id):

    client = get_accessible_client_or_404(
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

    log_client_audit(
        client_id=client.id,
        action_type="status",
        action="changed",
        title="Client status changed",
        description=(
            f"From: {old_status}\n"
            f"To: {new_status}"
            + (
                f"\nRemarks: {remarks}"
                if remarks
                else ""
            )
        )
    )

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

    client = get_accessible_client_or_404(
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
    # -----------------------------------------

    activity_contact_date = activity_date.date()

    if (
        client.last_contact_date is None
        or activity_contact_date >= client.last_contact_date
    ):
        client.last_contact_date = activity_contact_date

    try:
        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "ADD ACTIVITY ERROR:",
            repr(error)
        )

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
# ADD CLIENT NOTE / REMARK
# =========================================================

@clients_bp.route(
    "/<int:client_id>/notes/add",
    methods=["POST"]
)
@login_required
def add_note(client_id):

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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

    client = get_accessible_client_or_404(
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


# =========================================================
# EXPORT CLIENT RECORD - PDF
# =========================================================

@clients_bp.route(
    "/<int:client_id>/export/pdf"
)
@login_required
def export_client_pdf(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    data = get_client_export_data(
        client
    )

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=(
            f"Client Record - "
            f"{client.company_name}"
        ),
        author="Freight CRM",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )

    section_style = ParagraphStyle(
        "ExportSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#B91C1C"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "ExportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    small_style = ParagraphStyle(
        "ExportSmall",
        parent=body_style,
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#64748B"),
    )

    story = [
        Paragraph(
            "FREIGHT CRM - CLIENT RECORD",
            title_style
        ),
        Paragraph(
            (
                f"{export_text(client.company_name)}"
                f" &nbsp; | &nbsp; "
                f"Client ID #{client.id}"
                f" &nbsp; | &nbsp; "
                f"Exported "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ),
            small_style
        ),
        Spacer(1, 7 * mm),
        Paragraph(
            "Client Profile",
            section_style
        ),
    ]

    profile_rows = [
        ["Field", "Value"]
    ]

    for label, value in data["profile"]:
        profile_rows.append([
            label,
            export_text(value)
        ])

    story.append(
        pdf_table(
            profile_rows,
            [48 * mm, 205 * mm],
            body_style
        )
    )

    sections = []

    activity_rows = [
        [
            "Date",
            "Type",
            "Subject",
            "Description",
            "Created By",
        ]
    ]

    for item in data["activities"]:
        activity_rows.append([
            export_date(item.activity_date),
            export_label(item.activity_type),
            item.subject,
            item.description,
            (
                item.created_by.full_name
                if item.created_by
                else ""
            ),
        ])

    sections.append(
        ("Activities / Communication", activity_rows)
    )

    note_rows = [
        [
            "Created",
            "Note / Remark",
            "Created By",
        ]
    ]

    for item in data["notes"]:
        note_rows.append([
            export_date(item.created_at),
            item.note_text,
            (
                item.created_by.full_name
                if item.created_by
                else ""
            ),
        ])

    sections.append(
        ("Notes / Remarks", note_rows)
    )

    task_rows = [
        [
            "Due",
            "Task",
            "Type",
            "Priority",
            "Status",
            "Assigned To",
            "Description",
        ]
    ]

    for item in data["tasks"]:
        task_rows.append([
            export_date(item.due_date),
            item.title,
            export_label(item.task_type),
            export_label(item.priority),
            export_label(item.status),
            (
                item.assigned_to.full_name
                if getattr(
                    item,
                    "assigned_to",
                    None
                )
                else ""
            ),
            item.description,
        ])

    sections.append(
        ("Tasks / Follow-Ups", task_rows)
    )

    document_rows = [
        [
            "Uploaded",
            "File Name",
            "Type",
            "Uploaded By",
        ]
    ]

    for item in data["documents"]:
        document_rows.append([
            export_date(item.uploaded_at),
            item.original_filename,
            export_text(item.file_type).upper(),
            (
                item.uploaded_by.full_name
                if item.uploaded_by
                else ""
            ),
        ])

    sections.append(
        ("Documents Summary", document_rows)
    )

    status_rows = [
        [
            "Changed",
            "From",
            "To",
            "Changed By",
            "Remarks",
        ]
    ]

    for item in data["status_history"]:
        status_rows.append([
            export_date(item.changed_at),
            export_label(
                item.old_status,
                CLIENT_STATUSES
            ),
            export_label(
                item.new_status,
                CLIENT_STATUSES
            ),
            (
                item.changed_by.full_name
                if item.changed_by
                else ""
            ),
            item.remarks,
        ])

    sections.append(
        ("Status History", status_rows)
    )

    pipeline_rows = [
        [
            "Moved",
            "From",
            "To",
            "Moved By",
            "Remarks",
        ]
    ]

    for item in data["pipeline_history"]:
        pipeline_rows.append([
            export_date(item.moved_at),
            export_label(
                item.old_stage,
                PIPELINE_STAGES
            ),
            export_label(
                item.new_stage,
                PIPELINE_STAGES
            ),
            (
                item.moved_by.full_name
                if item.moved_by
                else ""
            ),
            item.remarks,
        ])

    sections.append(
        ("Pipeline History", pipeline_rows)
    )

    audit_rows = [
        [
            "Date",
            "Action Type",
            "Action",
            "Title",
            "Performed By",
            "Description",
        ]
    ]

    for item in data["audit_logs"]:
        audit_rows.append([
            export_date(item.created_at),
            export_label(item.action_type),
            export_label(item.action),
            item.title,
            (
                item.performed_by.full_name
                if getattr(
                    item,
                    "performed_by",
                    None
                )
                else ""
            ),
            item.description,
        ])

    sections.append(
        ("Permanent Audit History", audit_rows)
    )

    enquiry_rows = [
        [
            "ID",
            "Reference",
            "Date",
            "Status",
            "Mode",
            "Origin",
            "Destination",
        ]
    ]

    for item in data["enquiries"]:
        enquiry_rows.append([
            item.id,
            getattr(
                item,
                "enquiry_reference",
                getattr(
                    item,
                    "reference_number",
                    ""
                )
            ),
            export_date(
                getattr(
                    item,
                    "enquiry_date",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "mode_of_transport",
                    getattr(
                        item,
                        "shipment_mode",
                        None
                    )
                )
            ),
            getattr(
                item,
                "origin",
                ""
            ),
            getattr(
                item,
                "destination",
                ""
            ),
        ])

    sections.append(
        ("Linked Enquiries", enquiry_rows)
    )

    quotation_rows = [
        [
            "ID",
            "Quotation No.",
            "Enquiry ID",
            "Status",
            "Created",
            "Total",
        ]
    ]

    for item in data["quotations"]:
        quotation_rows.append([
            item.id,
            getattr(
                item,
                "quotation_number",
                getattr(
                    item,
                    "quote_number",
                    ""
                )
            ),
            item.enquiry_id,
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_date(
                getattr(
                    item,
                    "created_at",
                    None
                )
            ),
            getattr(
                item,
                "total_amount",
                getattr(
                    item,
                    "grand_total",
                    ""
                )
            ),
        ])

    sections.append(
        ("Linked Quotations", quotation_rows)
    )

    shipment_rows = [
        [
            "ID",
            "Shipment No.",
            "Status",
            "Mode",
            "Origin",
            "Destination",
            "Created",
        ]
    ]

    for item in data["shipments"]:
        shipment_rows.append([
            item.id,
            getattr(
                item,
                "shipment_number",
                getattr(
                    item,
                    "reference_number",
                    ""
                )
            ),
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "mode_of_transport",
                    getattr(
                        item,
                        "shipment_mode",
                        None
                    )
                )
            ),
            getattr(
                item,
                "origin",
                ""
            ),
            getattr(
                item,
                "destination",
                ""
            ),
            export_date(
                getattr(
                    item,
                    "created_at",
                    None
                )
            ),
        ])

    sections.append(
        ("Linked Shipments", shipment_rows)
    )

    for title, rows in sections:
        story.extend([
            Paragraph(
                title,
                section_style
            ),
            pdf_table(
                rows,
                [
                    (
                        255 * mm
                        / len(rows[0])
                    )
                ] * len(rows[0]),
                body_style
            ),
        ])

    document.build(
        story
    )

    buffer.seek(0)

    filename = (
        f"{export_safe_filename(client.company_name)}"
        f"_client_record.pdf"
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


# =========================================================
# EXPORT CLIENT RECORD - EXCEL
# =========================================================

@clients_bp.route(
    "/<int:client_id>/export/excel"
)
@login_required
def export_client_excel(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    data = get_client_export_data(
        client
    )

    workbook = Workbook()

    # Profile
    ws = workbook.active

    excel_prepare_sheet(
        ws,
        "Client Profile",
        ["Field", "Value"]
    )

    for label, value in data["profile"]:
        ws.append([
            label,
            export_text(value)
        ])

    excel_finish_sheet(ws)

    # Activities
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Activities",
        [
            "Date",
            "Type",
            "Subject",
            "Description",
            "Created By",
        ]
    )

    for item in data["activities"]:
        ws.append([
            export_date(item.activity_date),
            export_label(item.activity_type),
            item.subject,
            item.description,
            (
                item.created_by.full_name
                if item.created_by
                else ""
            ),
        ])

    excel_finish_sheet(ws)

    # Notes
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Notes",
        [
            "Created",
            "Note / Remark",
            "Created By",
        ]
    )

    for item in data["notes"]:
        ws.append([
            export_date(item.created_at),
            item.note_text,
            (
                item.created_by.full_name
                if item.created_by
                else ""
            ),
        ])

    excel_finish_sheet(ws)

    # Tasks
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Tasks",
        [
            "Due",
            "Task",
            "Type",
            "Priority",
            "Status",
            "Assigned To",
            "Description",
        ]
    )

    for item in data["tasks"]:
        ws.append([
            export_date(item.due_date),
            item.title,
            export_label(item.task_type),
            export_label(item.priority),
            export_label(item.status),
            (
                item.assigned_to.full_name
                if getattr(
                    item,
                    "assigned_to",
                    None
                )
                else ""
            ),
            item.description,
        ])

    excel_finish_sheet(ws)

    # Documents
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Documents",
        [
            "Uploaded",
            "File Name",
            "Type",
            "Uploaded By",
        ]
    )

    for item in data["documents"]:
        ws.append([
            export_date(item.uploaded_at),
            item.original_filename,
            export_text(item.file_type).upper(),
            (
                item.uploaded_by.full_name
                if item.uploaded_by
                else ""
            ),
        ])

    excel_finish_sheet(ws)

    # Status History
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Status History",
        [
            "Changed",
            "From",
            "To",
            "Changed By",
            "Remarks",
        ]
    )

    for item in data["status_history"]:
        ws.append([
            export_date(item.changed_at),
            export_label(
                item.old_status,
                CLIENT_STATUSES
            ),
            export_label(
                item.new_status,
                CLIENT_STATUSES
            ),
            (
                item.changed_by.full_name
                if item.changed_by
                else ""
            ),
            item.remarks,
        ])

    excel_finish_sheet(ws)

    # Pipeline History
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Pipeline History",
        [
            "Moved",
            "From",
            "To",
            "Moved By",
            "Remarks",
        ]
    )

    for item in data["pipeline_history"]:
        ws.append([
            export_date(item.moved_at),
            export_label(
                item.old_stage,
                PIPELINE_STAGES
            ),
            export_label(
                item.new_stage,
                PIPELINE_STAGES
            ),
            (
                item.moved_by.full_name
                if item.moved_by
                else ""
            ),
            item.remarks,
        ])

    excel_finish_sheet(ws)

    # Audit
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Audit History",
        [
            "Date",
            "Action Type",
            "Action",
            "Title",
            "Performed By",
            "Description",
        ]
    )

    for item in data["audit_logs"]:
        ws.append([
            export_date(item.created_at),
            export_label(item.action_type),
            export_label(item.action),
            item.title,
            (
                item.performed_by.full_name
                if getattr(
                    item,
                    "performed_by",
                    None
                )
                else ""
            ),
            item.description,
        ])

    excel_finish_sheet(ws)

    # Enquiries
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Enquiries",
        [
            "ID",
            "Reference",
            "Date",
            "Status",
            "Mode",
            "Origin",
            "Destination",
        ]
    )

    for item in data["enquiries"]:
        ws.append([
            item.id,
            getattr(
                item,
                "enquiry_reference",
                getattr(
                    item,
                    "reference_number",
                    ""
                )
            ),
            export_date(
                getattr(
                    item,
                    "enquiry_date",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "mode_of_transport",
                    getattr(
                        item,
                        "shipment_mode",
                        None
                    )
                )
            ),
            getattr(item, "origin", ""),
            getattr(item, "destination", ""),
        ])

    excel_finish_sheet(ws)

    # Quotations
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Quotations",
        [
            "ID",
            "Quotation No.",
            "Enquiry ID",
            "Status",
            "Created",
            "Total",
        ]
    )

    for item in data["quotations"]:
        ws.append([
            item.id,
            getattr(
                item,
                "quotation_number",
                getattr(
                    item,
                    "quote_number",
                    ""
                )
            ),
            item.enquiry_id,
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_date(
                getattr(
                    item,
                    "created_at",
                    None
                )
            ),
            getattr(
                item,
                "total_amount",
                getattr(
                    item,
                    "grand_total",
                    ""
                )
            ),
        ])

    excel_finish_sheet(ws)

    # Shipments
    ws = workbook.create_sheet()

    excel_prepare_sheet(
        ws,
        "Shipments",
        [
            "ID",
            "Shipment No.",
            "Status",
            "Mode",
            "Origin",
            "Destination",
            "Created",
        ]
    )

    for item in data["shipments"]:
        ws.append([
            item.id,
            getattr(
                item,
                "shipment_number",
                getattr(
                    item,
                    "reference_number",
                    ""
                )
            ),
            export_label(
                getattr(
                    item,
                    "status",
                    None
                )
            ),
            export_label(
                getattr(
                    item,
                    "mode_of_transport",
                    getattr(
                        item,
                        "shipment_mode",
                        None
                    )
                )
            ),
            getattr(item, "origin", ""),
            getattr(item, "destination", ""),
            export_date(
                getattr(
                    item,
                    "created_at",
                    None
                )
            ),
        ])

    excel_finish_sheet(ws)

    buffer = io.BytesIO()

    workbook.save(
        buffer
    )

    buffer.seek(0)

    filename = (
        f"{export_safe_filename(client.company_name)}"
        f"_client_record.xlsx"
    )

    return send_file(
        buffer,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


# =========================================================
# VIEW CLIENT
# =========================================================

@clients_bp.route("/<int:client_id>")
@login_required
def view_client(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    active_users = (
        db.session.execute(
            db.select(User)
            .where(
                User.is_active_user.is_(True)
            )
            .order_by(
                User.full_name.asc()
            )
        )
        .scalars()
        .all()
    )

    # =====================================================
    # ADMIN MERGE CANDIDATES
    # Active clients only + current source client excluded
    # =====================================================

    merge_candidates = []

    if is_admin_user():
        merge_candidates = (
            db.session.execute(
                db.select(Client)
                .where(
                    Client.id != client.id,
                    Client.is_archived.is_(False)
                )
                .order_by(
                    Client.company_name.asc(),
                    Client.contact_person_name.asc(),
                    Client.id.asc()
                )
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
    # PIPELINE / FUNNEL MOVEMENTS
    # -----------------------------------------

    for movement in client.pipeline_history:

        old_label = (
            dict(PIPELINE_STAGES).get(
                movement.old_stage,
                "Not Started"
            )
        )

        new_label = (
            dict(PIPELINE_STAGES).get(
                movement.new_stage,
                movement.new_stage.replace(
                    "_",
                    " "
                ).title()
            )
        )

        client_history.append({
            "type": "pipeline",
            "date": movement.moved_at,
            "title": (
                f"Pipeline moved: "
                f"{old_label} → {new_label}"
            ),
            "description": movement.remarks,
            "actor": (
                movement.moved_by.full_name
                if movement.moved_by
                else "Unknown User"
            ),
            "meta": "Pipeline Movement",
            "icon": "diagram-3-fill",
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
    # PERMANENT AUDIT LOGS
    # -----------------------------------------

    audit_logs = (
        db.session.execute(
            db.select(ClientAuditLog)
            .where(
                ClientAuditLog.client_id == client.id
            )
            .order_by(
                ClientAuditLog.created_at.desc()
            )
        )
        .scalars()
        .all()
    )

    for audit in audit_logs:

        client_history.append({
            "type": "audit",
            "date": audit.created_at,
            "title": audit.title,
            "description": audit.description,
            "actor": (
                audit.performed_by.full_name
                if getattr(audit, "performed_by", None)
                else "Unknown User"
            ),
            "meta": (
                f"{audit.action_type.replace('_', ' ').title()} • "
                f"{audit.action.replace('_', ' ').title()}"
            ),
            "icon": "shield-check",
        })

    # =====================================================
    # CLIENT-LINKED ENQUIRIES
    # =====================================================

    client_enquiries = (
        db.session.execute(
            db.select(Enquiry)
            .where(
                Enquiry.client_id == client.id
            )
            .order_by(
                Enquiry.enquiry_date.desc(),
                Enquiry.id.desc()
            )
        )
        .scalars()
        .all()
    )

    # =====================================================
    # CLIENT-LINKED QUOTATIONS
    # Quotation -> Enquiry -> Client
    # =====================================================

    client_quotations = (
        db.session.execute(
            db.select(Quotation)
            .join(
                Enquiry,
                Quotation.enquiry_id == Enquiry.id
            )
            .where(
                Enquiry.client_id == client.id
            )
            .order_by(
                Quotation.created_at.desc(),
                Quotation.id.desc()
            )
        )
        .scalars()
        .all()
    )

    # =====================================================
    # CLIENT-LINKED SHIPMENTS
    # =====================================================

    client_shipments = (
        db.session.execute(
            db.select(Shipment)
            .where(
                Shipment.client_id == client.id
            )
            .order_by(
                Shipment.created_at.desc(),
                Shipment.id.desc()
            )
        )
        .scalars()
        .all()
    )

    # -----------------------------------------
    # NEWEST FIRST
    # Safe handling for mixed naive/aware DB dates
    # -----------------------------------------

    def history_sort_key(item):
        value = item.get("date")

        if value is None:
            return datetime.min.replace(
                tzinfo=timezone.utc
            )

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(
                    tzinfo=timezone.utc
                )

            return value.astimezone(
                timezone.utc
            )

        return datetime.combine(
            value,
            datetime.min.time(),
            tzinfo=timezone.utc
        )

    client_history.sort(
        key=history_sort_key,
        reverse=True
    )

    pipeline_stage_values = [
        value
        for value, label
        in PIPELINE_STAGES
    ]

    current_pipeline_index = (
        pipeline_stage_values.index(
            client.pipeline_stage
        )
        if client.pipeline_stage
        in pipeline_stage_values
        else None
    )

    if current_pipeline_index is None:
        allowed_pipeline_stages = [
            PIPELINE_STAGES[0]
        ]
    elif client.pipeline_stage in {
        "won",
        "lost",
    }:
        allowed_pipeline_stages = []
    else:
        allowed_indexes = {
            current_pipeline_index - 1,
            current_pipeline_index + 1,
        }

        allowed_pipeline_stages = [
            stage
            for index, stage
            in enumerate(PIPELINE_STAGES)
            if index in allowed_indexes
        ]

    return render_template(
        "clients/view.html",
        client=client,
        client_history=client_history,
        pipeline_stages=PIPELINE_STAGES,
        allowed_pipeline_stages=allowed_pipeline_stages,
        merge_candidates=merge_candidates,

        # Client-linked commercial records
        client_enquiries=client_enquiries,
        client_quotations=client_quotations,
        client_shipments=client_shipments,

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
        owner_assignees=active_users,

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
@clients_bp.route(
    "/<int:client_id>/portal-account",
    methods=["POST"]
)
@login_required
def create_portal_account(client_id):

    client = get_accessible_client_or_404(client_id)

    existing = ClientPortalUser.query.filter_by(
        client_id=client.id
    ).first()

    if existing:
        flash(
            "Portal account already exists.",
            "warning"
        )
        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash(
            "Email and password are required.",
            "danger"
        )
        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    account = ClientPortalUser(
        client_id=client.id,
        email=email,
    )

    account.set_password(password)

    db.session.add(account)
    db.session.commit()

    flash(
        "Portal account created successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
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
        old_owner_id = client.assigned_to_id
        old_company_name = client.company_name
        old_category = client.category

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

        edit_changes = []

        if old_company_name != company_name:
            edit_changes.append(
                f"Company name: {old_company_name} -> {company_name}"
            )

        if old_category != category:
            edit_changes.append(
                f"Category: {old_category} -> {category}"
            )

        if old_owner_id != assigned_to_id:
            old_owner = db.session.get(
                User,
                old_owner_id
            )
            edit_changes.append(
                "Owner: "
                + (
                    old_owner.full_name
                    if old_owner
                    else "Unassigned"
                )
                + f" -> {assigned_owner.full_name}"
            )

        log_client_audit(
            client_id=client.id,
            action_type="client_record",
            action="updated",
            title="Client record updated",
            description=(
                "\n".join(edit_changes)
                if edit_changes
                else "Client profile details updated."
            )
        )

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
# MERGE DUPLICATE CLIENT RECORDS
# Admin only + single transaction + permanent audit
#
# Source duplicate is merged INTO target/master client.
# Linked records are reassigned before source deletion.
# =========================================================

@clients_bp.route(
    "/<int:client_id>/merge",
    methods=["POST"]
)
@login_required
def merge_client(client_id):

    source_client = db.get_or_404(
        Client,
        client_id
    )

    if not is_admin_user():
        flash(
            "Only Admin users can merge client records.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_client.id
            )
        )

    target_client_id = request.form.get(
        "target_client_id",
        type=int
    )

    remarks = request.form.get(
        "remarks",
        ""
    ).strip() or None

    if not target_client_id:
        flash(
            "Please select a master client record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_client.id
            )
        )

    if target_client_id == source_client.id:
        flash(
            "A client record cannot be merged into itself.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_client.id
            )
        )

    target_client = db.session.get(
        Client,
        target_client_id
    )

    if not target_client:
        flash(
            "Selected master client record was not found.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_client.id
            )
        )

    if target_client.is_archived:
        flash(
            "An archived client cannot be used as the master record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_client.id
            )
        )

    source_id = source_client.id
    source_name = source_client.company_name
    target_id = target_client.id
    target_name = target_client.company_name

    try:
        # -------------------------------------------------
        # Capture counts for permanent audit description
        # -------------------------------------------------

        transfer_counts = {
            "status_history": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientStatusHistory)
                .where(ClientStatusHistory.client_id == source_id)
            ) or 0,

            "pipeline_history": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientPipelineHistory)
                .where(ClientPipelineHistory.client_id == source_id)
            ) or 0,

            "attachments": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientAttachment)
                .where(ClientAttachment.client_id == source_id)
            ) or 0,

            "activities": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientActivity)
                .where(ClientActivity.client_id == source_id)
            ) or 0,

            "notes": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientNote)
                .where(ClientNote.client_id == source_id)
            ) or 0,

            "tasks": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientTask)
                .where(ClientTask.client_id == source_id)
            ) or 0,

            "audit_logs": db.session.scalar(
                db.select(db.func.count())
                .select_from(ClientAuditLog)
                .where(ClientAuditLog.client_id == source_id)
            ) or 0,

            "enquiries": db.session.scalar(
                db.select(db.func.count())
                .select_from(Enquiry)
                .where(Enquiry.client_id == source_id)
            ) or 0,

            "shipments": db.session.scalar(
                db.select(db.func.count())
                .select_from(Shipment)
                .where(Shipment.client_id == source_id)
            ) or 0,
        }

        # -------------------------------------------------
        # Reassign every direct client foreign key
        # -------------------------------------------------

        db.session.execute(
            db.update(ClientStatusHistory)
            .where(
                ClientStatusHistory.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientPipelineHistory)
            .where(
                ClientPipelineHistory.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientAttachment)
            .where(
                ClientAttachment.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientActivity)
            .where(
                ClientActivity.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientNote)
            .where(
                ClientNote.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientTask)
            .where(
                ClientTask.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(ClientAuditLog)
            .where(
                ClientAuditLog.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(Enquiry)
            .where(
                Enquiry.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        db.session.execute(
            db.update(Shipment)
            .where(
                Shipment.client_id == source_id
            )
            .values(
                client_id=target_id
            )
        )

        # Force FK moves before deleting duplicate source.
        db.session.flush()

        # -------------------------------------------------
        # Verify no supported direct links remain
        # -------------------------------------------------

        remaining_links = 0

        for model in (
            ClientStatusHistory,
            ClientPipelineHistory,
            ClientAttachment,
            ClientActivity,
            ClientNote,
            ClientTask,
            ClientAuditLog,
            Enquiry,
            Shipment,
        ):
            remaining_links += (
                db.session.scalar(
                    db.select(db.func.count())
                    .select_from(model)
                    .where(model.client_id == source_id)
                )
                or 0
            )

        if remaining_links:
            raise RuntimeError(
                "Merge verification failed: "
                f"{remaining_links} linked record(s) "
                "still reference the duplicate client."
            )

        # -------------------------------------------------
        # Preserve useful source profile values only when
        # target/master value is empty.
        # -------------------------------------------------

        if not target_client.secondary_phone:
            target_client.secondary_phone = (
                source_client.secondary_phone
            )

        if not target_client.website_url:
            target_client.website_url = (
                source_client.website_url
            )

        if not target_client.address_line_2:
            target_client.address_line_2 = (
                source_client.address_line_2
            )

        if not target_client.industry_sector:
            target_client.industry_sector = (
                source_client.industry_sector
            )

        if not target_client.lead_source:
            target_client.lead_source = (
                source_client.lead_source
            )

        if not target_client.last_contact_date:
            target_client.last_contact_date = (
                source_client.last_contact_date
            )
        elif (
            source_client.last_contact_date
            and source_client.last_contact_date
            > target_client.last_contact_date
        ):
            target_client.last_contact_date = (
                source_client.last_contact_date
            )

        if not target_client.next_follow_up_date:
            target_client.next_follow_up_date = (
                source_client.next_follow_up_date
            )
        elif (
            source_client.next_follow_up_date
            and source_client.next_follow_up_date
            < target_client.next_follow_up_date
        ):
            target_client.next_follow_up_date = (
                source_client.next_follow_up_date
            )

        # Merge JSON list values without duplicates.
        target_services = list(
            target_client.services_needed or []
        )

        for service in (
            source_client.services_needed or []
        ):
            if service not in target_services:
                target_services.append(service)

        target_client.services_needed = target_services

        target_tags = list(
            target_client.tags or []
        )

        for tag in (
            source_client.tags or []
        ):
            if tag not in target_tags:
                target_tags.append(tag)

        target_client.tags = target_tags

        # -------------------------------------------------
        # Permanent audit entry on surviving master client
        # -------------------------------------------------

        transfer_summary = (
            f"Duplicate source: {source_name} "
            f"(ID {source_id})\n"
            f"Master target: {target_name} "
            f"(ID {target_id})\n"
            f"Transferred status history: "
            f"{transfer_counts['status_history']}\n"
            f"Transferred pipeline history: "
            f"{transfer_counts['pipeline_history']}\n"
            f"Transferred attachments: "
            f"{transfer_counts['attachments']}\n"
            f"Transferred activities: "
            f"{transfer_counts['activities']}\n"
            f"Transferred notes: "
            f"{transfer_counts['notes']}\n"
            f"Transferred tasks: "
            f"{transfer_counts['tasks']}\n"
            f"Transferred prior audit logs: "
            f"{transfer_counts['audit_logs']}\n"
            f"Transferred enquiries: "
            f"{transfer_counts['enquiries']}\n"
            f"Transferred shipments: "
            f"{transfer_counts['shipments']}"
            + (
                f"\nRemarks: {remarks}"
                if remarks
                else ""
            )
        )

        log_client_audit(
            client_id=target_id,
            action_type="client_merge",
            action="duplicate_merged",
            title="Duplicate client merged",
            description=transfer_summary
        )

        db.session.flush()

        # -------------------------------------------------
        # Delete duplicate only after successful transfer
        # and verification. Master client survives.
        # -------------------------------------------------

        db.session.delete(
            source_client
        )

        db.session.flush()
        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "MERGE CLIENT ERROR:",
            repr(error)
        )

        flash(
            "Unable to merge the duplicate client record. "
            "No merge changes were saved.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=source_id
            )
        )

    flash(
        f"{source_name} was merged into "
        f"{target_name} successfully.",
        "success"
    )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=target_id
        )
    )


# =========================================================
# ARCHIVE CLIENT
# Admin only + permanent audit
# =========================================================

@clients_bp.route(
    "/<int:client_id>/archive",
    methods=["POST"]
)
@login_required
def archive_client(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    if not is_admin_user():
        flash(
            "Only Admin users can archive client records.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    if client.is_archived:
        flash(
            "This client is already archived.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.client_list"
            )
        )

    try:
        client.is_archived = True

        log_client_audit(
            client_id=client.id,
            action_type="client_record",
            action="archived",
            title="Client record archived",
            description=(
                f"Client: {client.company_name}"
            )
        )

        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print(
            "ARCHIVE CLIENT ERROR:",
            repr(error)
        )

        flash(
            "Unable to archive the client record.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    flash(
        f"{client.company_name} was archived.",
        "success"
    )

    return redirect(
    url_for(
        "clients.view_client",
        client_id=client.id
    )
)
    # =========================================================
# PERMANENT DELETE CLIENT
# Admin only + archived only + linked record protection
# =========================================================

@clients_bp.route(
    "/<int:client_id>/delete-permanently",
    methods=["POST"]
)
@login_required
def delete_client_permanently(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    # -----------------------------------------------------
    # SECURITY: ADMIN ONLY
    # -----------------------------------------------------

    if not is_admin_user():
        flash(
            "Only Admin users can permanently delete client records.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    # -----------------------------------------------------
    # SAFETY: CLIENT MUST BE ARCHIVED FIRST
    # -----------------------------------------------------

    if not client.is_archived:
        flash(
            "Archive the client before permanent deletion.",
            "warning"
        )

        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    # -----------------------------------------------------
    # EXACT COMPANY NAME CONFIRMATION
    # -----------------------------------------------------

    confirmation_name = request.form.get(
        "confirmation_name",
        ""
    ).strip()

    if confirmation_name != client.company_name:
        flash(
            "Company name confirmation does not match.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.client_list"
            )
        )

    # -----------------------------------------------------
    # PROTECT LINKED COMMERCIAL RECORDS
    # -----------------------------------------------------

    enquiry_count = (
        db.session.scalar(
            db.select(
                db.func.count()
            )
            .select_from(
                Enquiry
            )
            .where(
                Enquiry.client_id == client.id
            )
        )
        or 0
    )

    shipment_count = (
        db.session.scalar(
            db.select(
                db.func.count()
            )
            .select_from(
                Shipment
            )
            .where(
                Shipment.client_id == client.id
            )
        )
        or 0
    )

    if enquiry_count or shipment_count:

        blocked_records = []

        if enquiry_count:
            blocked_records.append(
                f"{enquiry_count} enquiry(s)"
            )

        if shipment_count:
            blocked_records.append(
                f"{shipment_count} shipment(s)"
            )

        flash(
            "Permanent deletion blocked. "
            "This client has linked commercial records: "
            + ", ".join(blocked_records)
            + ".",
            "danger"
        )

        return redirect(
            url_for(
                "clients.client_list"
            )
        )

    # -----------------------------------------------------
    # CAPTURE PHYSICAL FILE PATHS BEFORE DB DELETE
    # -----------------------------------------------------

    attachment_paths = []

    for attachment in client.attachments:

        absolute_path = os.path.join(
            current_app.root_path,
            "static",
            attachment.file_path
        )

        attachment_paths.append(
            absolute_path
        )

    client_name = client.company_name

    # -----------------------------------------------------
    # PERMANENT DATABASE DELETE
    # -----------------------------------------------------

    try:

        db.session.delete(
            client
        )

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        print(
            "PERMANENT DELETE CLIENT ERROR:",
            repr(error)
        )

        flash(
            "Unable to permanently delete the client record. "
            "No deletion changes were saved.",
            "danger"
        )

        return redirect(
            url_for(
                "clients.client_list"
            )
        )

    # -----------------------------------------------------
    # DELETE PHYSICAL FILES ONLY AFTER DB COMMIT
    # -----------------------------------------------------

    file_cleanup_errors = []

    for absolute_path in attachment_paths:

        try:
            if os.path.exists(
                absolute_path
            ):
                os.remove(
                    absolute_path
                )

        except OSError as error:

            file_cleanup_errors.append(
                str(error)
            )

    # -----------------------------------------------------
    # SUCCESS MESSAGE
    # -----------------------------------------------------

    if file_cleanup_errors:

        flash(
            f"{client_name} was permanently deleted. "
            "Some physical attachment files could not be removed.",
            "warning"
        )

    else:

        flash(
            f"{client_name} was permanently deleted successfully.",
            "success"
        )

    return redirect(
        url_for(
            "clients.client_list"
        )
    )
  # =========================================================
# RESTORE ARCHIVED CLIENT
# Admin only
# =========================================================

@clients_bp.route(
    "/<int:client_id>/restore",
    methods=["POST"]
)
@login_required
def restore_client(client_id):

    client = get_accessible_client_or_404(
        client_id
    )

    if not is_admin_user():
        flash(
            "Only Admin users can restore archived clients.",
            "danger"
        )
        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    if not client.is_archived:
        flash(
            "This client is already active.",
            "info"
        )
        return redirect(
            url_for(
                "clients.view_client",
                client_id=client.id
            )
        )

    try:
        client.is_archived = False

        db.session.commit()

        flash(
            f"{client.company_name} restored successfully.",
            "success"
        )

    except Exception as error:
        db.session.rollback()

        print(
            "RESTORE CLIENT ERROR:",
            repr(error)
        )

        flash(
            "Unable to restore the client.",
            "danger"
        )

    return redirect(
        url_for(
            "clients.view_client",
            client_id=client.id
        )
    )
from flask import abort
from flask_login import current_user

from app import db
from app.models import Client, Enquiry, Quotation, ClientTask


def is_admin_user():
    return getattr(current_user, "role", None) == "admin"


def is_sales_user():
    return getattr(current_user, "role", None) in {
        "sales",
        "sales_executive",
    }


def require_admin_or_sales():
    if not (is_admin_user() or is_sales_user()):
        abort(403)


def scope_clients(query):
    if is_sales_user():
        query = query.where(
            Client.assigned_to_id == current_user.id
        )
    return query


def scope_enquiries(query):
    if is_sales_user():
        query = (
            query
            .join(Client, Enquiry.client_id == Client.id)
            .where(Client.assigned_to_id == current_user.id)
        )
    return query


def scope_quotations(query):
    if is_sales_user():
        query = (
            query
            .join(Enquiry, Quotation.enquiry_id == Enquiry.id)
            .join(Client, Enquiry.client_id == Client.id)
            .where(Client.assigned_to_id == current_user.id)
        )
    return query


def scope_tasks(query):
    if is_sales_user():
        query = (
            query
            .join(Client, ClientTask.client_id == Client.id)
            .where(Client.assigned_to_id == current_user.id)
        )
    return query


def get_client_or_404(client_id):
    client = db.get_or_404(Client, client_id)
    if is_sales_user() and client.assigned_to_id != current_user.id:
        abort(404)
    return client


def get_enquiry_or_404(enquiry_id):
    enquiry = db.get_or_404(Enquiry, enquiry_id)
    if is_sales_user():
        client = db.session.get(Client, enquiry.client_id)
        if not client or client.assigned_to_id != current_user.id:
            abort(404)
    return enquiry


def get_quotation_or_404(quotation_id):
    quotation = db.get_or_404(Quotation, quotation_id)
    if is_sales_user():
        enquiry = db.session.get(Enquiry, quotation.enquiry_id)
        client = (
            db.session.get(Client, enquiry.client_id)
            if enquiry else None
        )
        if not client or client.assigned_to_id != current_user.id:
            abort(404)
    return quotation


def get_task_or_404(task_id):
    task = db.get_or_404(ClientTask, task_id)
    if is_sales_user():
        client = db.session.get(Client, task.client_id)
        if not client or client.assigned_to_id != current_user.id:
            abort(404)
    return task

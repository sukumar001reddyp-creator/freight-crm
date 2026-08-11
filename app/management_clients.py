from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Client

management_clients_bp = Blueprint(
    "management_clients",
    __name__,
    url_prefix="/management-clients"
)

def is_admin_user():
    return getattr(current_user, "role", None) == "admin"

def is_sales_user():
    return getattr(current_user, "role", None) in {"sales", "sales_executive"}

@management_clients_bp.route("/<path:category_name>")
@login_required
def view_category(category_name):
    query = db.select(Client).where(Client.is_archived == False, Client.category == category_name)
    
    if is_sales_user():
        query = query.where(Client.assigned_to_id == current_user.id)
    elif not is_admin_user():
        abort(403)

    clients = db.session.execute(query.order_by(Client.company_name)).scalars().all()

    return render_template(
        "management_clients/list.html",
        clients=clients,
        category_name=category_name
    )

@management_clients_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_client():
    category_name = request.args.get("category", "Embassies")
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        contact_person_name = request.form.get("contact_person_name", "").strip()
        email = request.form.get("email", "").strip()
        primary_phone = request.form.get("primary_phone", "").strip()
        address_line_1 = request.form.get("address_line_1", "").strip()
        category = request.form.get("category", category_name).strip()

        if not company_name or not email or not primary_phone:
            flash("Company name, email and primary phone are required.", "danger")
            return render_template("management_clients/add.html", category_name=category_name)

        try:
            new_client = Client(
                company_name=company_name,
                contact_person_name=contact_person_name,
                email=email,
                primary_phone=primary_phone,
                address_line_1=address_line_1,
                category=category,
                status="active",
                assigned_to_id=current_user.id,
                created_by_id=current_user.id
            )
            db.session.add(new_client)
            db.session.commit()
            flash(f"Client {company_name} added successfully.", "success")
            return redirect(url_for("management_clients.view_category", category_name=category))
        except Exception as e:
            db.session.rollback()
            flash("Unable to add client record.", "danger")

    return render_template("management_clients/add.html", category_name=category_name)

@management_clients_bp.route("/edit/<int:client_id>", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = db.get_or_404(Client, client_id)
    if request.method == "POST":
        client.company_name = request.form.get("company_name", "").strip()
        client.contact_person_name = request.form.get("contact_person_name", "").strip()
        client.email = request.form.get("email", "").strip()
        client.primary_phone = request.form.get("primary_phone", "").strip()
        client.address_line_1 = request.form.get("address_line_1", "").strip()
        
        try:
            db.session.commit()
            flash("Client updated successfully.", "success")
            return redirect(url_for("management_clients.view_client", client_id=client.id))
        except Exception:
            db.session.rollback()
            flash("Unable to update client.", "danger")

    return render_template("management_clients/edit.html", client=client, category_name=client.category)

@management_clients_bp.route("/view/<int:client_id>")
@login_required
def view_client(client_id):
    client = db.get_or_404(Client, client_id)
    return render_template("management_clients/view.html", client=client)
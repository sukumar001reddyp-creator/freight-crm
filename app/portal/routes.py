# app/portal/routes.py
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from app.portal import portal_bp
# from flask_login import login_required, current_user  # later add auth
from app import db
from app.models import (
    Client,
    ClientPortalUser,
    Shipment,
    ClientAttachment,
    SupportTicket,
)

from app.portal.forms import (
    PortalLoginForm,
    SupportRequestForm,
)

# Dummy data for development (later replace with DB queries filtered by client)

@portal_bp.route("/")
@portal_bp.route("/dashboard")
def dashboard():

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    portal_client_id = session["portal_client_id"]

    shipments = (
        Shipment.query
        .filter_by(client_id=portal_client_id)
        .order_by(Shipment.created_at.desc())
        .all()
    )

    return render_template(
        "portal/dashboard.html",
        shipments=shipments
    )

@portal_bp.route("/shipment")
def shipment():

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    shipment_id = request.args.get("id", type=int)

    if shipment_id:

        shipment = Shipment.query.filter_by(
            id=shipment_id,
            client_id=session["portal_client_id"]
        ).first_or_404()

        return render_template(
            "portal/shipment.html",
            shipment=shipment
        )

    shipments = (
        Shipment.query
        .filter_by(client_id=session["portal_client_id"])
        .order_by(Shipment.created_at.desc())
        .all()
    )

    return render_template(
        "portal/shipment.html",
        shipments=shipments
    )

@portal_bp.route("/documents")
def documents():

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    attachments = (
        ClientAttachment.query
        .filter_by(
            client_id=session["portal_client_id"]
        )
        .order_by(
            ClientAttachment.uploaded_at.desc()
        )
        .all()
    )

    return render_template(
        "portal/documents.html",
        attachments=attachments
    )

@portal_bp.route("/support", methods=["GET", "POST"])
def support():

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    form = SupportRequestForm()

    if form.validate_on_submit():

        ticket = SupportTicket(
            client_id=session["portal_client_id"],
            subject=form.subject.data,
            message=form.message.data,
        )

        db.session.add(ticket)
        db.session.commit()

        flash(
            "Support request submitted successfully.",
            "success",
        )

        return redirect(url_for("portal.support"))

    tickets = (
        SupportTicket.query
        .filter_by(client_id=session["portal_client_id"])
        .order_by(SupportTicket.created_at.desc())
        .all()
    )

    return render_template(
        "portal/support.html",
        form=form,
        tickets=tickets,
    )

@portal_bp.route("/profile")
def profile():

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    client = Client.query.get_or_404(
        session["portal_client_id"]
    )

    return render_template(
        "portal/profile.html",
        client=client
    )

# Later: Add login, auth, etc.
@portal_bp.route("/login", methods=["GET", "POST"])
def login():

    form = PortalLoginForm()

    if form.validate_on_submit():

        user = ClientPortalUser.query.filter_by(
            email=form.username.data.strip().lower(),
            is_active=True
        ).first()

        if user and user.check_password(form.password.data):

            session["portal_user_id"] = user.id
            session["portal_client_id"] = user.client_id

            flash(
                "Welcome to Client Portal.",
                "success"
            )

            return redirect(
                url_for("portal.dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "portal/login.html",
        form=form
    )
@portal_bp.route("/logout")
def logout():

    session.pop("portal_user_id", None)
    session.pop("portal_client_id", None)

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect(url_for("portal.login"))

    return redirect(url_for("portal.login"))
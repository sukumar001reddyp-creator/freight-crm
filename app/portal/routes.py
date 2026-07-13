# app/portal/routes.py
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
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
    SupportMessage,
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
        status="waiting_admin",
)

        db.session.add(ticket)
        db.session.flush()

        message = SupportMessage(
    ticket_id=ticket.id,
    sender="client",
    message=form.message.data,
)

        db.session.add(message)
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
@portal_bp.route(
    "/support/<int:ticket_id>",
    methods=["GET", "POST"]
)
def support_ticket(ticket_id):

    if "portal_user_id" not in session:
        return redirect(url_for("portal.login"))

    ticket = SupportTicket.query.filter_by(
        id=ticket_id,
        client_id=session["portal_client_id"]
    ).first_or_404()

    if request.method == "POST":

        reply = request.form.get(
            "message",
            ""
        ).strip()

        if reply:

            db.session.add(

                SupportMessage(
                    ticket_id=ticket.id,
                    sender="client",
                    message=reply,
                )

            )

            ticket.status = "waiting_admin"

            db.session.commit()

            flash(
                "Reply sent successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "portal.support_ticket",
                    ticket_id=ticket.id,
                )
            )

    return render_template(
        "portal/support_ticket.html",
        ticket=ticket,
        messages=ticket.messages,
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
@portal_bp.route(
    "/change-password",
    methods=["POST"]
)
def change_password():

    portal_user_id = session.get("portal_user_id")

    if not portal_user_id:
        flash("Please login again.", "danger")
        return redirect(url_for("portal.login"))

    portal_user = ClientPortalUser.query.get_or_404(
        portal_user_id
    )

    current_password = request.form.get(
        "current_password",
        ""
    ).strip()

    new_password = request.form.get(
        "new_password",
        ""
    ).strip()

    confirm_password = request.form.get(
        "confirm_password",
        ""
    ).strip()

    if not portal_user.check_password(current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("portal.profile"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("portal.profile"))

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("portal.profile"))

    portal_user.set_password(new_password)

    db.session.commit()

    flash("Password changed successfully.", "success")

    return redirect(url_for("portal.profile"))
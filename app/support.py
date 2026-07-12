from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from flask_login import login_required

from app import db
from app.models import (
    SupportTicket,
    SupportMessage,
)

support_bp = Blueprint(
    "support",
    __name__,
    url_prefix="/support",
)


@support_bp.route("/")
@login_required
def admin_list():
    tickets = (
        SupportTicket.query
        .order_by(
            SupportTicket.created_at.desc()
        )
        .all()
    )

    open_count = (
        SupportTicket.query
        .filter(
            SupportTicket.status.in_(["waiting_admin", "open"])
        )
        .count()
    )

    return render_template(
        "support/index.html",
        tickets=tickets,
        open_count=open_count,
    )


@support_bp.route("/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def view_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)

    if request.method == "POST":
        reply = request.form.get("admin_reply", "").strip()

        if reply:
            message = SupportMessage(
                ticket_id=ticket.id,
                sender="admin",
                message=reply,
            )

            db.session.add(message)

            ticket.status = "waiting_client"

            db.session.commit()

            flash(
                "Reply sent successfully.",
                "success"
            )

        return redirect(
            url_for(
                "support.view_ticket",
                ticket_id=ticket.id,
            )
        )

    return render_template(
        "support/view.html",
        ticket=ticket,
        messages=ticket.messages,
    )


@support_bp.route("/<int:ticket_id>/close")
@login_required
def close_ticket(ticket_id):
    ticket = SupportTicket.query.get_or_404(ticket_id)

    ticket.status = "closed"

    db.session.commit()

    flash(
        "Ticket closed successfully.",
        "success"
    )

    return redirect(
        url_for(
            "support.view_ticket",
            ticket_id=ticket.id,
        )
    )
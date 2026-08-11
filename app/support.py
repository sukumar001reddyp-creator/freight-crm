from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from flask_login import login_required, current_user

from app import db
from app.models import (
    SupportTicket,
    SupportMessage,
    Client,
)

support_bp = Blueprint(
    "support",
    __name__,
    url_prefix="/support",
)


@support_bp.route("/")
@login_required
def admin_list():
    query = db.select(SupportTicket)
    
    # ఒకవేళ లాగిన్ అయిన యూజర్ 'sales_executive' అయితే, కేవలం వాళ్ళ అసైన్ అయిన క్లయింట్స్ టికెట్స్ మాత్రమే ఫిల్టర్ అవ్వాలి
    if getattr(current_user, "role", None) == "sales_executive":
        query = query.join(Client, SupportTicket.client_id == Client.id).where(Client.assigned_to_id == current_user.id)
    
    tickets = db.session.execute(query.order_by(SupportTicket.created_at.desc())).scalars().all()

    # ఓపెన్ టికెట్స్ కౌంట్ (సేల్స్ ఎగ్జిక్యూటివ్‌కి వాళ్ళవి మాత్రమే, మిగతావాళ్ళకి టోటల్ ఓపెన్ కౌంట్)
    if getattr(current_user, "role", None) == "sales_executive":
        open_count = sum(1 for t in tickets if t.status in ["waiting_admin", "open"])
        sidebar_support_count = open_count
    else:
        open_count = (
            SupportTicket.query
            .filter(
                SupportTicket.status.in_(["waiting_admin", "open"])
            )
            .count()
        )
        sidebar_support_count = open_count

    return render_template(
        "support/index.html",
        tickets=tickets,
        open_count=open_count,
        sidebar_support_count=sidebar_support_count,
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
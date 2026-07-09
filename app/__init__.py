from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    login_required,
)

from config import Config


# =========================================================
# EXTENSIONS
# =========================================================

db = SQLAlchemy()
login_manager = LoginManager()


# =========================================================
# APPLICATION FACTORY
# =========================================================

def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)


    # ==========================================
    # INITIALIZE EXTENSIONS
    # ==========================================

    db.init_app(app)
    login_manager.init_app(app)


    # ==========================================
    # LOGIN CONFIGURATION
    # ==========================================

    login_manager.login_view = "auth.login"

    login_manager.login_message = (
        "Please log in to access the CRM."
    )

    login_manager.login_message_category = "warning"


    # ==========================================
    # AUTH BLUEPRINT
    # ==========================================

    from app.auth import auth_bp

    app.register_blueprint(auth_bp)


    # ==========================================
    # CLIENTS BLUEPRINT
    # ==========================================

    from app.clients import clients_bp

    app.register_blueprint(clients_bp)


    # ==========================================
    # ENQUIRIES BLUEPRINT
    # ==========================================

    from app.enquiries import enquiries_bp

    app.register_blueprint(enquiries_bp)


    # ==========================================
    # QUOTATIONS BLUEPRINT
    # ==========================================

    from app.quotations import quotations_bp

    app.register_blueprint(quotations_bp)


    # ==========================================
    # SHIPMENTS BLUEPRINT
    # ==========================================

    from app.shipments import shipments_bp

    app.register_blueprint(shipments_bp)


    # ==========================================
    # TASKS & FOLLOW-UPS BLUEPRINT
    # ==========================================

    from app.tasks import tasks_bp

    app.register_blueprint(tasks_bp)


    # ==========================================
    # IMPORT MODELS
    # ==========================================

    from app import models

        # ==========================================
    # GLOBAL SIDEBAR COUNTS
    # Every template/page ki available
    # ==========================================

    @app.context_processor
    def inject_sidebar_counts():

        from app.models import (
            Client,
            Enquiry,
        )

        sidebar_clients_count = (
            Client.query
            .filter(
                Client.is_archived.is_(False)
            )
            .count()
        )

        sidebar_enquiries_count = (
            Enquiry.query
            .filter(
                Enquiry.status.notin_([
                    "closed",
                    "cancelled",
                    "converted",
                ])
            )
            .count()
        )

        return {
            "sidebar_clients_count": sidebar_clients_count,
            "sidebar_enquiries_count": sidebar_enquiries_count,
        }
    # ==========================================
    # HOME
    # ==========================================

    @app.route("/")
    def home():

        return redirect(
            url_for("dashboard")
        )

    
    # ==========================================
    # DASHBOARD
    # ==========================================

    @app.route("/dashboard")
    @login_required
    def dashboard():

        from app.models import (
            Client,
            Enquiry,
            Quotation,
            Shipment,
            ClientTask,
            ClientActivity,
        )

        # --------------------------------------
        # TOP CARDS
        # --------------------------------------

        total_clients = (
            Client.query
            .filter(
                Client.is_archived.is_(False)
            )
            .count()
        )

        total_enquiries = (
            Enquiry.query
            .filter(
                Enquiry.status.notin_([
                    "closed",
                    "cancelled",
                    "converted",
                ])
            )
            .count()
        )

        total_quotations = (
            Quotation.query
            .filter(
                Quotation.status == "pending"
            )
            .count()
        )

        total_shipments = (
            Shipment.query
            .filter(
                Shipment.shipment_status.notin_([
                    "delivered",
                    "closed",
                    "completed",
                    "closed_completed",
                ])
            )
            .count()
        )


        # --------------------------------------
        # SHIPMENT STATUS FLOW
        #
        # Existing DB currently uses "active".
        # We include "active" in Booked so an
        # active shipment is visible immediately.
        # --------------------------------------

                # --------------------------------------
        # SHIPMENT CURRENT WORKFLOW STAGE COUNTS
        # --------------------------------------

        from app.models import ShipmentMilestone

        shipment_stage_order = [
            "booking_confirmed",
            "pickup",
            "origin_handling",
            "in_transit",
            "arrival",
            "customs_clearance",
            "delivery",
            "closed",
        ]

        shipment_stage_counts = {
            stage: 0
            for stage in shipment_stage_order
        }

        all_shipments = Shipment.query.all()

        for shipment in all_shipments:

            completed_stages = {
                milestone.stage
                for milestone in ShipmentMilestone.query.filter_by(
                    shipment_id=shipment.id
                ).all()
            }

            # Closed shipment
            if "closed" in completed_stages:
                shipment_stage_counts["closed"] += 1
                continue

            # Find first incomplete stage = current/next stage
            current_stage = None

            for stage in shipment_stage_order:

                if stage not in completed_stages:
                    current_stage = stage
                    break

            # All stages completed
            if current_stage is None:
                current_stage = "closed"

            shipment_stage_counts[current_stage] += 1


        # --------------------------------------
        # FOLLOW-UPS / TASKS
        # --------------------------------------

        follow_up_tasks = (
            ClientTask.query
            .filter(
                ClientTask.status.in_([
                    "pending",
                    "in_progress",
                ])
            )
            .order_by(
                ClientTask.due_date.asc()
            )
            .limit(5)
            .all()
        )

        pending_followups_count = (
            ClientTask.query
            .filter(
                ClientTask.status.in_([
                    "pending",
                    "in_progress",
                ])
            )
            .count()
        )


        # --------------------------------------
        # CLIENT LIFECYCLE COUNTS
        # Only non-archived clients
        # --------------------------------------

        def client_status_count(*statuses):

            return (
                Client.query
                .filter(
                    Client.is_archived.is_(False),
                    Client.status.in_(statuses),
                )
                .count()
            )

        lifecycle_counts = {
            "lead": client_status_count(
                "lead",
                "prospect",
            ),
            "new": client_status_count(
                "new",
            ),
            "active": client_status_count(
                "active",
                "existing",
            ),
            "key": client_status_count(
                "key",
                "strategic",
            ),
            "at_risk": client_status_count(
                "at_risk",
            ),
            "dormant": client_status_count(
                "dormant",
                "inactive",
            ),
            "churned": client_status_count(
                "churned",
                "lost",
            ),
            "reactivated": client_status_count(
                "reactivated",
                "win_back",
            ),
            "referral": client_status_count(
                "referral",
            ),
        }


        # --------------------------------------
        # RECENT ACTIVITY TIMELINE
        # --------------------------------------

        recent_activities = (
            ClientActivity.query
            .order_by(
                ClientActivity.activity_date.desc(),
                ClientActivity.id.desc(),
            )
            .limit(6)
            .all()
        )


        # --------------------------------------
        # RENDER DASHBOARD
        # --------------------------------------

        return render_template(
            "dashboard/index.html",

            total_clients=total_clients,
            total_enquiries=total_enquiries,
            total_quotations=total_quotations,
            total_shipments=total_shipments,

            shipment_stage_counts=shipment_stage_counts,

            follow_up_tasks=follow_up_tasks,
            pending_followups_count=pending_followups_count,

            lifecycle_counts=lifecycle_counts,

            recent_activities=recent_activities,
        )


    # ==========================================
    # RETURN FLASK APP
    # ==========================================

    return app

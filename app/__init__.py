from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.permissions import permissions

from flask_login import (
    LoginManager,
    login_required,
    current_user,
)

from config import Config


# =========================================================
# EXTENSIONS
# =========================================================

db = SQLAlchemy()
migrate = Migrate()
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
    migrate.init_app(app, db)
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
    # ADMIN USERS & ROLES BLUEPRINT
    # ==========================================

    from app.users import users_bp

    app.register_blueprint(users_bp)

    from app.portal import portal_bp

    app.register_blueprint(
    portal_bp
    )


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
        from flask_login import current_user

        client_count_query = Client.query.filter(
            Client.is_archived.is_(False)
        )

        enquiry_count_query = Enquiry.query.join(
            Client,
            Enquiry.client_id == Client.id
        ).filter(
            Enquiry.status.notin_([
                "closed",
                "cancelled",
                "converted",
            ])
        )

        if getattr(current_user, "role", None) in {
            "sales",
            "sales_executive",
        }:
            client_count_query = client_count_query.filter(
                Client.assigned_to_id == current_user.id
            )
            enquiry_count_query = enquiry_count_query.filter(
                Client.assigned_to_id == current_user.id
            )

        sidebar_clients_count = client_count_query.count()
        sidebar_enquiries_count = enquiry_count_query.count()

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
        # ROLE-SCOPED DASHBOARD
        # Admin sees all data.
        # Sales Executive sees only data linked
        # to clients assigned to that salesperson.
        # --------------------------------------

        is_sales_dashboard = (
            getattr(current_user, "role", None)
            in {"sales", "sales_executive"}
        )

        client_scope = Client.query.filter(
            Client.is_archived.is_(False)
        )
        enquiry_scope = Enquiry.query.join(
            Client,
            Enquiry.client_id == Client.id
        )
        quotation_scope = Quotation.query.join(
            Enquiry,
            Quotation.enquiry_id == Enquiry.id
        ).join(
            Client,
            Enquiry.client_id == Client.id
        )
        task_scope = ClientTask.query.join(
            Client,
            ClientTask.client_id == Client.id
        )
        activity_scope = ClientActivity.query.join(
            Client,
            ClientActivity.client_id == Client.id
        )
        shipment_scope = Shipment.query.join(
            Client,
            Shipment.client_id == Client.id
        )

        if is_sales_dashboard:
            client_scope = client_scope.filter(
                Client.assigned_to_id == current_user.id
            )
            enquiry_scope = enquiry_scope.filter(
                Client.assigned_to_id == current_user.id
            )
            quotation_scope = quotation_scope.filter(
                Client.assigned_to_id == current_user.id
            )
            task_scope = task_scope.filter(
                Client.assigned_to_id == current_user.id
            )
            activity_scope = activity_scope.filter(
                Client.assigned_to_id == current_user.id
            )
            shipment_scope = shipment_scope.filter(
                Client.assigned_to_id == current_user.id
            )

        # --------------------------------------
        # TOP CARDS
        # --------------------------------------

        total_clients = client_scope.count()

        total_enquiries = enquiry_scope.filter(
            Enquiry.status.notin_(["closed", "cancelled", "converted"])
        ).count()

        total_quotations = quotation_scope.filter(
            Quotation.status == "pending"
        ).count()

        total_shipments = shipment_scope.filter(
            Shipment.shipment_status.notin_([
                "delivered",
                "closed",
                "completed",
                "closed_completed",
            ])
        ).count()

        # --------------------------------------
        # DOCUMENT-ALIGNED DASHBOARD REPORTING
        # --------------------------------------
        quotation_status_counts = {
            "pending": quotation_scope.filter(Quotation.status == "pending").count(),
            "approved": quotation_scope.filter(Quotation.status == "approved").count(),
            "rejected": quotation_scope.filter(Quotation.status == "rejected").count(),
        }

        enquiry_status_counts = {
            "open": total_enquiries,
            "converted": enquiry_scope.filter(Enquiry.status == "converted").count(),
            "closed": enquiry_scope.filter(
                Enquiry.status.in_(["closed", "cancelled"])
            ).count(),
        }

        closed_shipments_count = shipment_scope.filter(
            Shipment.shipment_status.in_([
                "delivered",
                "closed",
                "completed",
                "closed_completed",
            ])
        ).count()

        client_category_counts = {}
        category_query = (
            db.session.query(Client.category, db.func.count(Client.id))
            .filter(Client.is_archived.is_(False))
        )
        if is_sales_dashboard:
            category_query = category_query.filter(
                Client.assigned_to_id == current_user.id
            )
        category_rows = (
            category_query
            .group_by(Client.category)
            .all()
        )
        for category_name, category_count in category_rows:
            label = str(category_name).strip() if category_name else "Uncategorized"
            client_category_counts[label] = category_count


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
            "booked",
            "cargo_picked_up",
            "in_transit",
            "arrived_destination",
            "customs_clearance",
            "out_for_delivery",
            "delivered",
            "closed_completed",
        ]

        shipment_stage_counts = {
            stage: 0
            for stage in shipment_stage_order
        }

        all_shipments = shipment_scope.all()

        for shipment in all_shipments:

            completed_stages = {
                milestone.stage
                for milestone in ShipmentMilestone.query.filter_by(
                    shipment_id=shipment.id
                ).all()
            }

            # Closed shipment
            if (
                "closed_completed" in completed_stages
                or "closed" in completed_stages
            ):
                shipment_stage_counts["closed_completed"] += 1
                continue

            # Find first incomplete stage = current/next stage
            current_stage = None

            for stage in shipment_stage_order:

                if stage not in completed_stages:
                    current_stage = stage
                    break

            # All stages completed
            if current_stage is None:
                current_stage = "closed_completed"

            if current_stage in shipment_stage_counts:
                shipment_stage_counts[current_stage] += 1


        # --------------------------------------
        # FOLLOW-UPS / TASKS
        # --------------------------------------

        follow_up_tasks = (
            task_scope
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
            task_scope
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
                client_scope
                .filter(
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
            activity_scope
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

            quotation_status_counts=quotation_status_counts,
            enquiry_status_counts=enquiry_status_counts,
            closed_shipments_count=closed_shipments_count,
            client_category_counts=client_category_counts,
        )


    # ==========================================
    # RETURN FLASK APP
    # ==========================================
    @app.context_processor
    def inject_permissions():
        return {
            "permissions": permissions
        }

    return app

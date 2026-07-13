from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
    
)
from apscheduler.schedulers.background import BackgroundScheduler
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
    # BLUEPRINTS
    # ==========================================

    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.clients import clients_bp
    app.register_blueprint(clients_bp)

    from app.enquiries import enquiries_bp
    app.register_blueprint(enquiries_bp)

    from app.quotations import quotations_bp
    app.register_blueprint(quotations_bp)

    from app.shipments import shipments_bp
    app.register_blueprint(shipments_bp)

    from app.tasks import tasks_bp
    app.register_blueprint(tasks_bp)

    from app.users import users_bp
    app.register_blueprint(users_bp)

    from app.portal import portal_bp
    app.register_blueprint(portal_bp)

    from app.support import support_bp
    app.register_blueprint(support_bp)

    from app.backup import backup_bp
    app.register_blueprint(backup_bp)

    from app.reports import reports_bp
    app.register_blueprint(reports_bp)
    # ==========================================
    # IMPORT MODELS
    # ==========================================

    from app import models


    # ==========================================
    # GLOBAL SIDEBAR COUNTS
    # ==========================================

    @app.context_processor
    def inject_sidebar_counts():

        from app.models import (
            Client,
            Enquiry,
            SupportTicket,
        )
        from flask_login import current_user

        client_count_query = Client.query.filter(
            Client.is_archived.is_(False)
        )

        enquiry_count_query = (
            Enquiry.query.join(
                Client,
                Enquiry.client_id == Client.id
            )
            .filter(
                Enquiry.status.notin_(["closed", "cancelled", "converted"])
            )
        )

        if getattr(current_user, "role", None) in {"sales", "sales_executive"}:
            client_count_query = client_count_query.filter(
                Client.assigned_to_id == current_user.id
            )
            enquiry_count_query = enquiry_count_query.filter(
                Client.assigned_to_id == current_user.id
            )

        try:
            sidebar_clients_count = client_count_query.count()
            sidebar_enquiries_count = enquiry_count_query.count()

            sidebar_support_count = SupportTicket.query.filter(
                SupportTicket.status.in_(["waiting_admin", "open"])
            ).count()

        except Exception:
            sidebar_clients_count = 0
            sidebar_enquiries_count = 0
            sidebar_support_count = 0

        return {
            "sidebar_clients_count": sidebar_clients_count,
            "sidebar_enquiries_count": sidebar_enquiries_count,
            "sidebar_support_count": sidebar_support_count,
        }


    # ==========================================
    # HOME
    # ==========================================

    @app.route("/")
    def home():
        return redirect(url_for("dashboard"))


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
            ShipmentMilestone,
            ClientTask,
            ClientActivity,
        )

        is_sales_dashboard = getattr(current_user, "role", None) in {"sales", "sales_executive"}

        client_scope = Client.query.filter(Client.is_archived.is_(False))
        enquiry_scope = Enquiry.query.join(Client, Enquiry.client_id == Client.id)
        quotation_scope = Quotation.query.join(Enquiry, Quotation.enquiry_id == Enquiry.id).join(Client, Enquiry.client_id == Client.id)
        task_scope = ClientTask.query.join(Client, ClientTask.client_id == Client.id)
        activity_scope = ClientActivity.query.join(Client, ClientActivity.client_id == Client.id)
        shipment_scope = Shipment.query.join(Client, Shipment.client_id == Client.id)

        if is_sales_dashboard:
            client_scope = client_scope.filter(Client.assigned_to_id == current_user.id)
            enquiry_scope = enquiry_scope.filter(Client.assigned_to_id == current_user.id)
            quotation_scope = quotation_scope.filter(Client.assigned_to_id == current_user.id)
            task_scope = task_scope.filter(Client.assigned_to_id == current_user.id)
            activity_scope = activity_scope.filter(Client.assigned_to_id == current_user.id)
            shipment_scope = shipment_scope.filter(Client.assigned_to_id == current_user.id)

        # Top Cards
        total_clients = client_scope.count()
        total_enquiries = enquiry_scope.filter(Enquiry.status.notin_(["closed", "cancelled", "converted"])).count()
        total_quotations = quotation_scope.filter(Quotation.status == "pending").count()
        total_shipments = shipment_scope.filter(Shipment.shipment_status.notin_(["delivered", "closed", "completed", "closed_completed"])).count()

        # Quotation Status
        quotation_status_counts = {
            "pending": quotation_scope.filter(Quotation.status == "pending").count(),
            "approved": quotation_scope.filter(Quotation.status == "approved").count(),
            "rejected": quotation_scope.filter(Quotation.status == "rejected").count(),
        }

        # Enquiry Status
        enquiry_status_counts = {
            "open": total_enquiries,
            "converted": enquiry_scope.filter(Enquiry.status == "converted").count(),
            "closed": enquiry_scope.filter(Enquiry.status.in_(["closed", "cancelled"])).count(),
        }

        closed_shipments_count = shipment_scope.filter(
            Shipment.shipment_status.in_(["delivered", "closed", "completed", "closed_completed"])
        ).count()

        # Client Categories
        client_category_counts = {}
        category_query = db.session.query(Client.category, db.func.count(Client.id)).filter(Client.is_archived.is_(False))
        if is_sales_dashboard:
            category_query = category_query.filter(Client.assigned_to_id == current_user.id)
        for category_name, count in category_query.group_by(Client.category).all():
            label = str(category_name).strip() if category_name else "Uncategorized"
            client_category_counts[label] = count

        # Shipment Stages (simplified)
        shipment_stage_counts = {
            "booked": shipment_scope.filter(Shipment.current_stage == "booked").count(),
            "cargo_picked_up": shipment_scope.filter(Shipment.current_stage == "cargo_picked_up").count(),
            "in_transit": shipment_scope.filter(Shipment.current_stage == "in_transit").count(),
            "arrived_destination": shipment_scope.filter(Shipment.current_stage == "arrived_destination").count(),
            "customs_clearance": shipment_scope.filter(Shipment.current_stage == "customs_clearance").count(),
            "out_for_delivery": shipment_scope.filter(Shipment.current_stage == "out_for_delivery").count(),
            "delivered": shipment_scope.filter(Shipment.current_stage == "delivered").count(),
            "closed_completed": shipment_scope.filter(Shipment.current_stage == "closed_completed").count(),
        }

        
        # Follow-ups
        follow_up_tasks = task_scope.filter(ClientTask.status.in_(["pending", "in_progress"])).order_by(ClientTask.due_date.asc()).limit(5).all()
        pending_followups_count = task_scope.filter(ClientTask.status.in_(["pending", "in_progress"])).count()

        # Lifecycle Counts
        def client_status_count(*statuses):
            return client_scope.filter(Client.status.in_(statuses)).count()

        lifecycle_counts = {
            "lead": client_status_count("lead", "prospect"),
            "new": client_status_count("new"),
            "active": client_status_count("active", "existing"),
            "key": client_status_count("key", "strategic"),
            "at_risk": client_status_count("at_risk"),
            "dormant": client_status_count("dormant", "inactive"),
            "churned": client_status_count("churned", "lost"),
            "reactivated": client_status_count("reactivated", "win_back"),
            "referral": client_status_count("referral"),
        }

        # Recent Activities
        recent_activities = activity_scope.order_by(ClientActivity.activity_date.desc(), ClientActivity.id.desc()).limit(6).all()
                # Recent Activities
        recent_activities = activity_scope.order_by(
            ClientActivity.activity_date.desc(),
            ClientActivity.id.desc()
        ).limit(6).all()

        # Shipment Stage Counts
        print(shipment_stage_counts)

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
    # PERMISSIONS
    # ==========================================

    @app.context_processor
    def inject_permissions():
        return {
            "permissions": permissions
        }
    
    return app
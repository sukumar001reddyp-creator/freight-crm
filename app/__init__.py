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

    login_manager.login_view = (
        "auth.login"
    )

    login_manager.login_message = (
        "Please log in to access the CRM."
    )

    login_manager.login_message_category = (
        "warning"
    )


    # ==========================================
    # AUTH BLUEPRINT
    # ==========================================

    from app.auth import auth_bp

    app.register_blueprint(
        auth_bp
    )


    # ==========================================
    # CLIENTS BLUEPRINT
    # ==========================================

    from app.clients import clients_bp

    app.register_blueprint(
        clients_bp
    )


    # ==========================================
    # ENQUIRIES BLUEPRINT
    # ==========================================

    from app.enquiries import enquiries_bp

    app.register_blueprint(
        enquiries_bp
    )


    # ==========================================
    # QUOTATIONS BLUEPRINT
    # ==========================================

    from app.quotations import quotations_bp

    app.register_blueprint(
        quotations_bp
    )


    # ==========================================
    # SHIPMENTS BLUEPRINT
    # ==========================================

    from app.shipments import shipments_bp

    app.register_blueprint(
        shipments_bp
    )


    # ==========================================
    # IMPORT MODELS
    #
    # SQLAlchemy ki all models register
    # avvadaniki import chestunnam.
    # ==========================================

    from app import models


    # ==========================================
    # HOME
    # ==========================================

    @app.route("/")
    def home():

        return redirect(
            url_for(
                "dashboard"
            )
        )


    # ==========================================
    # DASHBOARD
    # ==========================================

    @app.route("/dashboard")
    @login_required
    def dashboard():

        return render_template(
            "dashboard/index.html"
        )


    # ==========================================
    # RETURN FLASK APP
    # ==========================================

    return app
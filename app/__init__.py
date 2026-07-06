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


db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Login configuration
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
    # IMPORT MODELS
    # ==========================================

    from app import models


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
        return render_template(
            "dashboard/index.html"
        )


    return app
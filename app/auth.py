from app import db
from app.models import User
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)

from app.models import User


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        remember = (
            request.form.get("remember")
            == "on"
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            user
            and user.check_password(password)
            and user.is_active_user
        ):
            login_user(
                user,
                remember=remember
            )

            flash(
                "Welcome back!",
                "success"
            )

            next_page = request.args.get("next")

            if next_page:
                return redirect(next_page)

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "auth/login.html"
    )
@auth_bp.route(
    "/change-password",
    methods=["GET", "POST"]
)
@login_required
def change_password():

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Current password verify
        if not current_user.check_password(
            current_password
        ):
            flash(
                "Current password is incorrect.",
                "danger"
            )

            return render_template(
                "auth/change_password.html"
            )

        # Minimum password length
        if len(new_password) < 8:
            flash(
                "New password must be at least 8 characters.",
                "danger"
            )

            return render_template(
                "auth/change_password.html"
            )

        # Same old password prevent
        if current_user.check_password(
            new_password
        ):
            flash(
                "New password must be different from current password.",
                "danger"
            )

            return render_template(
                "auth/change_password.html"
            )

        # Confirm password
        if new_password != confirm_password:
            flash(
                "New password and confirmation do not match.",
                "danger"
            )

            return render_template(
                "auth/change_password.html"
            )

        try:
            current_user.set_password(
                new_password
            )

            db.session.commit()

        except Exception:
            db.session.rollback()

            flash(
                "Unable to change password. Please try again.",
                "danger"
            )

            return render_template(
                "auth/change_password.html"
            )

        flash(
            "Password changed successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "auth/change_password.html"
    )
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("auth.login")
    )
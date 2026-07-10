from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import User
from app.permissions import roles_required, ROLE_ADMIN


users_bp = Blueprint(
    "users",
    __name__,
    url_prefix="/users"
)


ROLE_OPTIONS = [
    ("admin", "Admin"),
    ("sales_executive", "Sales Executive"),
    ("operations_team", "Operations Team"),
    ("management_viewer", "Management / Viewer"),
]


@users_bp.route("/")
@login_required
@roles_required(ROLE_ADMIN)
def user_list():
    users = User.query.order_by(
        User.is_active_user.desc(),
        User.full_name.asc()
    ).all()

    return render_template(
        "users/index.html",
        users=users,
        role_options=ROLE_OPTIONS,
    )


@users_bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_ADMIN)
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        if not full_name or not email or not password:
            flash("Full name, email and password are required.", "danger")
            return render_template(
                "users/form.html",
                user=None,
                role_options=ROLE_OPTIONS,
            )

        if role not in dict(ROLE_OPTIONS):
            flash("Please select a valid role.", "danger")
            return render_template(
                "users/form.html",
                user=None,
                role_options=ROLE_OPTIONS,
            )

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template(
                "users/form.html",
                user=None,
                role_options=ROLE_OPTIONS,
            )

        existing = User.query.filter(
            db.func.lower(User.email) == email
        ).first()

        if existing:
            flash("A user with this email already exists.", "danger")
            return render_template(
                "users/form.html",
                user=None,
                role_options=ROLE_OPTIONS,
            )

        user = User(
            full_name=full_name,
            email=email,
            role=role,
            is_active_user=True,
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("User account created successfully.", "success")
        return redirect(url_for("users.user_list"))

    return render_template(
        "users/form.html",
        user=None,
        role_options=ROLE_OPTIONS,
    )


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_ADMIN)
def edit_user(user_id):
    user = db.get_or_404(User, user_id)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "").strip()

        if not full_name or not email:
            flash("Full name and email are required.", "danger")
            return render_template(
                "users/form.html",
                user=user,
                role_options=ROLE_OPTIONS,
            )

        if role not in dict(ROLE_OPTIONS):
            flash("Please select a valid role.", "danger")
            return render_template(
                "users/form.html",
                user=user,
                role_options=ROLE_OPTIONS,
            )

        duplicate = User.query.filter(
            db.func.lower(User.email) == email,
            User.id != user.id,
        ).first()

        if duplicate:
            flash("A user with this email already exists.", "danger")
            return render_template(
                "users/form.html",
                user=user,
                role_options=ROLE_OPTIONS,
            )

        # Prevent current admin from accidentally removing own admin role.
        if user.id == current_user.id and role != "admin":
            flash("You cannot remove your own Admin role.", "danger")
            return render_template(
                "users/form.html",
                user=user,
                role_options=ROLE_OPTIONS,
            )

        user.full_name = full_name
        user.email = email
        user.role = role

        db.session.commit()

        flash("User details updated successfully.", "success")
        return redirect(url_for("users.user_list"))

    return render_template(
        "users/form.html",
        user=user,
        role_options=ROLE_OPTIONS,
    )


@users_bp.route("/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@roles_required(ROLE_ADMIN)
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)

    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("users.user_list"))

    user.is_active_user = not user.is_active_user
    db.session.commit()

    flash(
        f"{user.full_name} is now "
        f"{'Active' if user.is_active_user else 'Inactive'}.",
        "success"
    )
    return redirect(url_for("users.user_list"))


@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@login_required
@roles_required(ROLE_ADMIN)
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get("new_password", "")

    if len(new_password) < 8:
        flash("New password must be at least 8 characters.", "danger")
        return redirect(url_for("users.user_list"))

    user.set_password(new_password)
    db.session.commit()

    flash(f"Password reset successfully for {user.full_name}.", "success")
    return redirect(url_for("users.user_list"))

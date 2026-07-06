import os

from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():

    # Create missing tables
    db.create_all()

    # Create default admin only if missing
    admin_email = "admin@freightcrm.com"

    admin = User.query.filter_by(
        email=admin_email
    ).first()

    if not admin:

        admin = User(
            full_name="CRM Administrator",
            email=admin_email,
            role="admin",
            is_active_user=True
        )

        admin.set_password(
            "Admin@123"
        )

        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
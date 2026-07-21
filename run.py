import os

from app import create_app, db
from app.models import User

app = create_app()

# Create default admin if it doesn't exist
with app.app_context():
    admin = User.query.filter_by(email="admin@freightcrm.com").first()

    if not admin:
        admin = User(
            full_name="Administrator",
            email="admin@freightcrm.com",
            role="admin",
            is_active_user=True
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin created.")
    else:
        print("✅ Default admin already exists.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
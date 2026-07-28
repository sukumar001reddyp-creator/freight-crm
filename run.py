import os

from app import create_app, db
from app.models import User

app = create_app()

# Create default admin if it doesn't exist and synchronize database columns
with app.app_context():
    try:
        with db.engine.connect() as connection:
            connection.execute(db.text('ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);'))
            connection.execute(db.text('ALTER TABLE shipment_documents ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255);'))
            connection.commit()
            print("✅ PostgreSQL columns synchronized successfully!")
    except Exception as e:
        print("Database sync note:", e)

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
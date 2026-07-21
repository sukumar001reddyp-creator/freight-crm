import os

from app import create_app, db
from app.models import User

app = create_app()




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
    # Deployment trigger - 2026-07-21
"""add current_stage to shipments

Revision ID: 05b9563dfaa1
Revises: e3dd43af21d0
Create Date: 2026-07-13 15:36:27.691084

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "05b9563dfaa1"
down_revision = "e3dd43af21d0"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("shipments", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "current_stage",
                sa.String(length=50),
                nullable=True,
                server_default="booked",
            )
        )


def downgrade():

    with op.batch_alter_table("shipments", schema=None) as batch_op:

        batch_op.drop_column("current_stage")
"""Add client_id to quotations

Revision ID: e494096bbf2a
Revises: b30a9f26d2d6
Create Date: 2026-07-20 12:52:24.852769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e494096bbf2a'
down_revision = 'b30a9f26d2d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('client_id', sa.Integer(), nullable=True)
        )

        batch_op.create_index(
            'ix_quotations_client_id',
            ['client_id'],
            unique=False
        )

        batch_op.create_foreign_key(
            'fk_quotations_client_id',
            'clients',
            ['client_id'],
            ['id'],
            ondelete='RESTRICT'
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('quotations', schema=None) as batch_op:

        batch_op.drop_constraint(
            'fk_quotations_client_id',
            type_='foreignkey'
        )

        batch_op.drop_index('ix_quotations_client_id')

        batch_op.drop_column('client_id')

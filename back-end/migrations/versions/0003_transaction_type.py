"""Add transactions.type ("debit" or "credit"). Existing rows were all expenses, so they become debits.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("type", sa.String(6), nullable=False, server_default="debit"))


def downgrade() -> None:
    op.drop_column("transactions", "type")

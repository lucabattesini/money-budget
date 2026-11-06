"""An index for the most common read: a family's transactions in a period (TKT-91).

Only an index, so no data changes. Making it takes a moment while the table is locked for writes.

Revision ID: 0022
Revises: 0021
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_transactions_family_date", "transactions", ["family_id", "transactioned_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_family_date", table_name="transactions")

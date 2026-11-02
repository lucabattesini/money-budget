"""Rename transactions.date to transactioned_at and add created_at / updated_at.

Before this, `date` was always the moment the row was saved, so it is also a good value for created_at
on old rows. updated_at stays empty (never edited).

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("transactions")}
    if "date" in columns and "transactioned_at" not in columns:
        op.alter_column("transactions", "date", new_column_name="transactioned_at")
    if "created_at" not in columns:
        op.add_column("transactions", sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
        # A row without a date still gets a created_at: the moment of this migration
        op.execute("UPDATE transactions SET created_at = COALESCE(transactioned_at, now())")
    if "updated_at" not in columns:
        op.add_column("transactions", sa.Column("updated_at", sa.DateTime()))


def downgrade() -> None:
    op.drop_column("transactions", "updated_at")
    op.drop_column("transactions", "created_at")
    op.alter_column("transactions", "transactioned_at", new_column_name="date")

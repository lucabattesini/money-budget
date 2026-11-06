"""Merchants: the place or company a transaction went to, as an optional setting of the family (TKT-58).

A new table, a nullable link on transactions (a transaction without a merchant stays valid, so existing data is
untouched) and a family switch that is off until the family turns it on.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.add_column("transactions", sa.Column("merchant_id", sa.Integer(), nullable=True))
    op.create_foreign_key("transactions_merchant_id_fkey", "transactions", "merchants", ["merchant_id"], ["id"])
    op.add_column("families", sa.Column("merchants_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("families", "merchants_enabled")
    op.drop_constraint("transactions_merchant_id_fkey", "transactions", type_="foreignkey")
    op.drop_column("transactions", "merchant_id")
    op.drop_table("merchants")

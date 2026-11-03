"""Budgets: how much a family plans to spend in a category from a month on.

One row per family, category and month, with the amount in integer cents. A plan stays in force until a later
month changes it (a month with no row follows the latest earlier one), and a row of 0 means "nothing from this month
on". Nothing existing changes.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.UniqueConstraint("family_id", "category_id", "month", name="uq_budgets_family_category_month"),
    )


def downgrade() -> None:
    op.drop_table("budgets")

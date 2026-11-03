"""Monthly budgets: how much a family plans to spend in a category in a month.

One row per family, category and month, with the amount in integer cents (more than zero: no budget is no row).
Nothing existing changes.

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

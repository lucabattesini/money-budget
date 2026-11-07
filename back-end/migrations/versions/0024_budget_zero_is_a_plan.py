"""A budget of 0 becomes a real plan; "no plan from here on" is now a missing amount.

Until now a row of 0 meant "stop the plan", so nobody could plan to spend nothing. Those rows are turned into rows with
no amount, which keeps their meaning. Going back turns them into 0 again (a real 0 plan then becomes a stop).

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("budgets", "amount", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE budgets SET amount = NULL WHERE amount = 0")


def downgrade() -> None:
    op.execute("UPDATE budgets SET amount = 0 WHERE amount IS NULL")
    op.alter_column("budgets", "amount", existing_type=sa.Integer(), nullable=False)

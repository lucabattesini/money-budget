"""Let a family choose its currency and its language.

Every family starts with what the app always showed: reais and Portuguese. The currency is only how amounts are
shown (they stay integer cents, nothing is converted); the language is the one the assistant answers in and the
format of numbers and dates.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("families", sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("families", sa.Column("language", sa.String(2), nullable=False, server_default="pt"))


def downgrade() -> None:
    op.drop_column("families", "language")
    op.drop_column("families", "currency")

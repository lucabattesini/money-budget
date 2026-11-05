"""Give each family a timezone.

A transaction's date and time are the wall-clock time of the family (TKT-65), so "now" has to be read on the family's
clock, not on the server's. Existing families get Brasília time, the setting that matches the reais and Portuguese they
started with; the dates already stored are left as they are.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "families",
        sa.Column("timezone", sa.String(length=40), nullable=False, server_default="America/Sao_Paulo"),
    )


def downgrade() -> None:
    op.drop_column("families", "timezone")

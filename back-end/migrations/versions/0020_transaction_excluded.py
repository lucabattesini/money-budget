"""A transaction can be left out of the totals (TKT-87).

A new yes/no on transactions that is "no" for every existing one, except the ones that are not spending: those in the
"Transferência" and "Pagamento de fatura do cartão" categories (of the group "Transferências"), which are now marked as
left out. "Ajustes de saldo", the third category of that group, is a correction and keeps counting.

Revision ID: 0020
Revises: 0019
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

GROUP = "Transferências"
NAMES = {"transferência", "pagamento de fatura do cartão"}


def _words(name: str) -> str:
    """The name without the emoji it starts with ("🔄 Transferência" -> "transferência"), as the app compares names."""
    return re.sub(r"^[^\w]+", "", name or "").strip().casefold()


def upgrade() -> None:
    op.add_column("transactions", sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.false()))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT c.id, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE g.name = :group"
        ),
        {"group": GROUP},
    ).all()
    ids = [row.id for row in rows if _words(row.name) in NAMES]
    if ids:
        connection.execute(
            sa.text("UPDATE transactions SET excluded = true WHERE category_id = ANY(:ids)").bindparams(
                sa.bindparam("ids", ids, type_=sa.ARRAY(sa.Uuid()))
            )
        )


def downgrade() -> None:
    op.drop_column("transactions", "excluded")

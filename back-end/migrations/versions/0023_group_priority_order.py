"""Show the category groups in order of priority: housing and bills first, what can be cut last.

Only the `position` of the groups changes; no category or amount moves. Groups that are not in the list keep their
place after these ones.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

NEW_ORDER = [
    "Receitas",
    "Moradia",
    "Contas e Serviços",
    "Alimentação",
    "Auto e Transporte",
    "Saúde e Bem-estar",
    "Filhos",
    "Educação",
    "Finanças",
    "Compras",
    "Viagem e Estilo de Vida",
    "Presentes e Doações",
    "Outros",
    "Transferências",
]


def upgrade() -> None:
    conn = op.get_bind()
    # Groups that are not in the list go after it, in the order they had
    others = [r.name for r in conn.execute(sa.text("SELECT name FROM category_groups ORDER BY position, id")) if r.name not in NEW_ORDER]
    for position, name in enumerate(NEW_ORDER + others, start=1):
        conn.execute(sa.text("UPDATE category_groups SET position = :p WHERE name = :n"), {"p": position, "n": name})


def downgrade() -> None:
    pass  # the old order is not worth restoring: it was only alphabetical by accident

"""Group the categories.

`category_groups` is a fixed set of headings, the same for everyone. Every category gets exactly one:
the default categories by name (the grouping below is a copy made on purpose, so this migration keeps working
whatever the app's list becomes later), and anything else, such as a category a family made, goes to "Outros".

The downgrade drops the groups; nothing else about the categories changes.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

GROUPS = {
    "Casa": ["Aluguel", "Contas Básicas", "Internet e Telefone", "Manutenção da Casa", "Pets"],
    "Alimentação": ["Supermercado", "Alimentação"],
    "Transporte": ["Transporte"],
    "Saúde e bem-estar": ["Saúde e Farmácia", "Cuidados Pessoais", "Exercícios e Esportes"],
    "Lazer": ["Entretenimento", "Hobbies", "Viagem", "Assinaturas", "Eventos Especiais"],
    "Educação": ["Educação"],
    "Compras e presentes": ["Compras", "Presentes e Doações"],
    "Finanças": ["Seguros", "Pagamento de Dívidas", "Impostos", "Emergências", "Fundo de Emergência", "Investimentos"],
    "Outros": ["Outros"],
}


def upgrade() -> None:
    conn = op.get_bind()
    groups = op.create_table(
        "category_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.bulk_insert(groups, [{"name": name} for name in GROUPS])
    ids = dict(conn.execute(sa.text("SELECT name, id FROM category_groups")).all())

    op.add_column("categories", sa.Column("group_id", sa.Integer(), sa.ForeignKey("category_groups.id")))
    for group, names in GROUPS.items():
        conn.execute(
            sa.text(
                "UPDATE categories SET group_id = :group WHERE family_id IS NULL "
                "AND lower(name) = ANY(SELECT lower(unnest(CAST(:names AS text[]))))"
            ),
            {"group": ids[group], "names": names},
        )
    # A category of a family, or a default one this list does not know
    conn.execute(sa.text("UPDATE categories SET group_id = :outros WHERE group_id IS NULL"), {"outros": ids["Outros"]})
    op.alter_column("categories", "group_id", nullable=False)


def downgrade() -> None:
    op.drop_column("categories", "group_id")
    op.drop_table("category_groups")

"""Replace transactions.category (the category id stored as text) with an integer category_id foreign key.

This is the hand-written migration the app used to run at start-up, now a proper revision.
Old rows hold the id as text, but the assistant used to fall back to the category name, so both are
understood; anything unknown goes to the "Outros" category.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {c["name"] for c in sa.inspect(connection).get_columns("transactions")}
    if "category_id" not in columns:
        op.add_column("transactions", sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")))

    if "category" in columns:
        categories = connection.execute(sa.text("SELECT id, name FROM categories")).all()
        ids = {c.id for c in categories}
        ids_by_name = {c.name.lower(): c.id for c in categories}
        fallback_id = ids_by_name.get("outros")

        for row in connection.execute(sa.text("SELECT id, category FROM transactions")).all():
            raw = (row.category or "").strip()
            if raw.isdigit() and int(raw) in ids:
                category_id = int(raw)
            else:
                category_id = ids_by_name.get(raw.lower(), fallback_id)
            connection.execute(
                sa.text("UPDATE transactions SET category_id = :category_id WHERE id = :id"),
                {"category_id": category_id, "id": row.id},
            )
        op.drop_column("transactions", "category")


def downgrade() -> None:
    op.add_column("transactions", sa.Column("category", sa.String(100)))
    op.execute("UPDATE transactions SET category = CAST(category_id AS VARCHAR) WHERE category_id IS NOT NULL")
    op.drop_column("transactions", "category_id")

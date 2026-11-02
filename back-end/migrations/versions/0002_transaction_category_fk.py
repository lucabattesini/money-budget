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

        def category_for(raw: str) -> int | None:
            if raw.isascii() and raw.isdigit() and int(raw) in ids:
                return int(raw)
            return ids_by_name.get(raw.lower(), fallback_id)

        # Work per distinct text, not per row: a table has thousands of rows but only a few dozen
        # different category texts, so this is a handful of UPDATE statements however big the table is.
        distinct = connection.execute(
            sa.text("SELECT DISTINCT btrim(category) FROM transactions WHERE btrim(category) <> ''")
        ).scalars()
        for raw in distinct.all():
            category_id = category_for(raw)
            if category_id is None:
                # The text is about to be dropped for good, so do not lose it quietly
                raise RuntimeError(
                    f"Some transactions have the category {raw!r}, which matches no category, and there is "
                    "no 'Outros' category to put them in. Add the default categories (python -m db.seed) and "
                    "run the upgrade again."
                )
            connection.execute(
                sa.text("UPDATE transactions SET category_id = :category_id WHERE btrim(category) = :raw"),
                {"category_id": category_id, "raw": raw},
            )
        if fallback_id is not None:  # no category at all: Outros
            connection.execute(
                sa.text("UPDATE transactions SET category_id = :category_id WHERE btrim(coalesce(category, '')) = ''"),
                {"category_id": fallback_id},
            )
        op.drop_column("transactions", "category")


def downgrade() -> None:
    op.add_column("transactions", sa.Column("category", sa.String(100)))
    op.execute("UPDATE transactions SET category = CAST(category_id AS VARCHAR) WHERE category_id IS NOT NULL")
    op.drop_column("transactions", "category_id")

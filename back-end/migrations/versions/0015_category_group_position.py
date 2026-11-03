"""Store the order of the category groups.

Until now the groups were listed in the order they were created in (by id), which nothing said out loud. Each group
now has a `position` (1 is first) that every list sorts by. Existing groups keep the order they had, so nothing moves.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("category_groups", sa.Column("position", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE category_groups SET position = ordered.n "
        "FROM (SELECT id, row_number() OVER (ORDER BY id) AS n FROM category_groups) AS ordered "
        "WHERE category_groups.id = ordered.id"
    )
    op.alter_column("category_groups", "position", nullable=False)


def downgrade() -> None:
    op.drop_column("category_groups", "position")

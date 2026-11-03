"""Keep a family for 30 days after its last person left, so they can go back.

`families.abandoned_at` is set when the last person leaves (by joining another family). A family that is
already empty when this runs is marked abandoned now, so it is cleaned up like the others instead of lingering
forever. `users.previous_family_id` remembers where a person who joined and started empty can go back to.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("families", sa.Column("abandoned_at", sa.DateTime()))
    op.add_column("users", sa.Column("previous_family_id", sa.Integer(), sa.ForeignKey("families.id")))
    op.execute(
        "UPDATE families SET abandoned_at = now() "
        "WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.family_id = families.id)"
    )


def downgrade() -> None:
    op.drop_column("users", "previous_family_id")
    op.drop_column("families", "abandoned_at")

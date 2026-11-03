"""Add family roles and invite codes.

`users.role` is `owner` or `member`. Everyone who exists today is alone in their own family, so everyone is an
owner. `family_invites` holds the codes an owner hands out; only a hash of each code is stored.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(10), nullable=False, server_default="owner"))
    op.create_table(
        "family_invites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_hint", sa.String(4), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("used_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("family_invites")
    op.drop_column("users", "role")

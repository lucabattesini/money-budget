"""Add the import_jobs table (a spreadsheet of transactions imported in steps).

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(255)),
        sa.Column("rows", sa.JSON()),
        sa.Column("category_map", sa.JSON()),
        sa.Column("total_rows", sa.Integer()),
        sa.Column("imported_count", sa.Integer()),
        sa.Column("skipped", sa.JSON()),
        sa.Column("error", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("queued_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")

"""Move ownership from the user to the family.

Every existing user gets a family of their own. Transactions and export jobs move to that family
(`transactions.user_id` stays and now means "who entered it"; export jobs get `requested_by`), and categories a user owned move to the user's family.
Default categories (no owner) stay shared. A transaction that pointed at another person's category loses
that category (it becomes uncategorised), so no family keeps seeing a category it cannot use. The old `user_id` columns of categories and export jobs are dropped.

Transactions with no user at all (`user_id` NULL) belonged to nobody and could never be read through the
API, so there is no family to give them: they are deleted. The app never wrote such rows.

The downgrade gives every table its `user_id` back: transactions never lost theirs, export jobs get it from
`requested_by`, categories from the lowest user id of the family. Families with several people cannot be
represented in the old schema, so there that last one is a best guess.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # One family per existing user
    op.add_column("users", sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id")))
    for user_id in conn.execute(sa.text("SELECT id FROM users ORDER BY id")).scalars().all():
        family_id = conn.execute(sa.text("INSERT INTO families DEFAULT VALUES RETURNING id")).scalar()
        conn.execute(sa.text("UPDATE users SET family_id = :f WHERE id = :u"), {"f": family_id, "u": user_id})
    op.alter_column("users", "family_id", nullable=False)

    # Transactions
    op.add_column("transactions", sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id")))
    op.execute("DELETE FROM transactions WHERE user_id IS NULL")
    op.execute("UPDATE transactions SET family_id = users.family_id FROM users WHERE users.id = transactions.user_id")
    op.alter_column("transactions", "family_id", nullable=False)
    op.alter_column("transactions", "user_id", nullable=False)

    # Categories (NULL stays NULL: a default category)
    op.add_column("categories", sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id")))
    op.execute("UPDATE categories SET family_id = users.family_id FROM users WHERE users.id = categories.user_id")
    op.drop_column("categories", "user_id")
    # A transaction could point at a category of someone else (nothing used to stop it). It must not keep
    # showing another family's private category, so it loses the category (a default one is fine).
    op.execute(
        "UPDATE transactions SET category_id = NULL FROM categories WHERE categories.id = transactions.category_id "
        "AND categories.family_id IS NOT NULL AND categories.family_id <> transactions.family_id"
    )

    # Export jobs
    op.add_column("export_jobs", sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id")))
    op.add_column("export_jobs", sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id")))
    op.execute(
        "UPDATE export_jobs SET requested_by = user_id, family_id = users.family_id "
        "FROM users WHERE users.id = export_jobs.user_id"
    )
    op.alter_column("export_jobs", "family_id", nullable=False)
    op.alter_column("export_jobs", "requested_by", nullable=False)
    op.drop_column("export_jobs", "user_id")


def downgrade() -> None:
    op.add_column("export_jobs", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")))
    op.execute("UPDATE export_jobs SET user_id = requested_by")
    op.alter_column("export_jobs", "user_id", nullable=False)
    op.drop_column("export_jobs", "requested_by")
    op.drop_column("export_jobs", "family_id")

    op.add_column("categories", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")))
    op.execute(
        "UPDATE categories SET user_id = (SELECT MIN(users.id) FROM users WHERE users.family_id = categories.family_id) "
        "WHERE family_id IS NOT NULL"
    )
    op.drop_column("categories", "family_id")

    op.alter_column("transactions", "user_id", nullable=True)
    op.drop_column("transactions", "family_id")

    op.drop_column("users", "family_id")
    op.drop_table("families")

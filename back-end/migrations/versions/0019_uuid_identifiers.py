"""Identify every row with a UUID instead of a counting number (TKT-74).

Each table gets a new key beside the old one, filled with a random UUID; every link (foreign key) is then re-pointed
through the old key, and only after that are the old keys dropped and the new ones made the primary keys. So every
row keeps what it was linked to: who owns what, which category a transaction has, budgets, invites, imports, exports.

Things to know before running it on real data:
- Take a copy of the database first. The tables are locked while it runs (it is one transaction, so a failure
  leaves the database as it was).
- Spreadsheet imports in progress are deleted: they keep ids inside their saved rows and are only kept for a day.
- Login tokens made before this hold the old number, so they stop working: everyone logs in again.
- The downgrade gives every row a counting number again (in an arbitrary but consistent order, not the old numbers)
  and keeps all the links. Imports in progress are deleted and tokens stop working again.

Revision ID: 0019
Revises: 0018
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

TABLES = [
    "families",
    "category_groups",
    "users",
    "merchants",
    "categories",
    "transactions",
    "family_invites",
    "budgets",
    "import_jobs",
    "export_jobs",
]

# (table, column, table it points at, may be empty)
LINKS = [
    ("users", "family_id", "families", False),
    ("users", "previous_family_id", "families", True),
    ("merchants", "family_id", "families", False),
    ("categories", "family_id", "families", True),
    ("categories", "group_id", "category_groups", False),
    ("transactions", "family_id", "families", False),
    ("transactions", "user_id", "users", False),
    ("transactions", "category_id", "categories", True),
    ("transactions", "merchant_id", "merchants", True),
    ("family_invites", "family_id", "families", False),
    ("family_invites", "created_by", "users", False),
    ("family_invites", "used_by", "users", True),
    ("budgets", "family_id", "families", False),
    ("budgets", "category_id", "categories", False),
    ("import_jobs", "family_id", "families", False),
    ("import_jobs", "requested_by", "users", False),
    ("export_jobs", "family_id", "families", False),
    ("export_jobs", "requested_by", "users", False),
]


def _convert(new_type: str) -> None:
    """Change every key and link to `new_type` ("uuid" or "integer"), keeping each row's links."""
    # 1. A new key beside each old one
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN new_id {new_type}")
        if new_type == "uuid":
            op.execute(f"UPDATE {table} SET new_id = gen_random_uuid()")
        else:
            op.execute(
                f"UPDATE {table} t SET new_id = n.number FROM "
                f"(SELECT id, row_number() OVER (ORDER BY id) AS number FROM {table}) n WHERE n.id = t.id"
            )
    # 2. A new link beside each old one, pointing at the new key of the same row
    for table, column, target, _empty in LINKS:
        op.execute(f"ALTER TABLE {table} ADD COLUMN new_{column} {new_type}")
        op.execute(f"UPDATE {table} t SET new_{column} = r.new_id FROM {target} r WHERE t.{column} = r.id")
    # 3. Drop the old links and keys. CASCADE also drops what hangs from them: the foreign keys, the sequences and
    #    the budgets' "one plan per family, category and month" rule (recreated below).
    for table, column, _target, _empty in LINKS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN {column} CASCADE")
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN id CASCADE")
    # 4. The new ones take their place
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN new_id TO id")
        op.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (id)")
        if new_type == "integer":
            op.execute(f"CREATE SEQUENCE {table}_id_seq OWNED BY {table}.id")
            op.execute(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
            op.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT nextval('{table}_id_seq')")
    for table, column, target, empty in LINKS:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN new_{column} TO {column}")
        if not empty:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_fkey FOREIGN KEY ({column}) REFERENCES {target} (id)"
        )
    op.execute(
        "ALTER TABLE budgets ADD CONSTRAINT uq_budgets_family_category_month UNIQUE (family_id, category_id, month)"
    )


def upgrade() -> None:
    # Their saved rows hold the old ids, and they are only kept for a day
    op.execute("DELETE FROM import_jobs")
    _convert("uuid")


def downgrade() -> None:
    op.execute("DELETE FROM import_jobs")
    _convert("integer")

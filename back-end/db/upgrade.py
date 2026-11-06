"""Bring the database to the latest schema: `python -m db.upgrade`.

Run by Docker start-up before the API. It is safe to run any number of times.

Databases created before Alembic have no `alembic_version` table. For those, the schema is inspected to
find which of the old hand-written changes it already has, the matching revision is recorded, and only
the missing revisions are applied.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from db.connection import DATABASE_URL

BACK_END = Path(__file__).resolve().parent.parent

# Any number; every process that migrates this database must use the same one
MIGRATION_LOCK_ID = 7_251_104


def alembic_config(url: str) -> Config:
    config = Config(str(BACK_END / "alembic.ini"))
    config.set_main_option("script_location", str(BACK_END / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # % is special in config values
    return config


def detect_revision(inspector) -> str | None:
    """Which revision a database without alembic_version is already at (None: an empty database)."""
    if not inspector.has_table("transactions"):
        others = [t for t in ("users", "categories") if inspector.has_table(t)]
        if others:
            raise RuntimeError(
                f"This database has the tables {others} but no 'transactions' table, so it cannot be told "
                "which migrations it already has. Fix or empty the database by hand, then run the upgrade again."
            )
        return None
    columns = {c["name"] for c in inspector.get_columns("transactions")}
    if "category_id" not in columns or "category" in columns:
        return "0001"  # still has the category stored as text (or half way through that change)
    if "type" not in columns:
        return "0002"
    if "transactioned_at" not in columns:
        return "0003"
    if not inspector.has_table("export_jobs"):
        return "0004"
    if "uq_users_whatsapp_phone" not in {u["name"] for u in inspector.get_unique_constraints("users")}:
        return "0005"
    if not inspector.has_table("families"):
        return "0006"
    if not inspector.has_table("family_invites"):
        return "0007"
    if "abandoned_at" not in {c["name"] for c in inspector.get_columns("families")}:
        return "0008"
    if not inspector.has_table("category_groups"):
        return "0009"
    if "currency" not in {c["name"] for c in inspector.get_columns("families")}:
        return "0010"
    if not inspector.has_table("budgets"):
        return "0013"
    if "position" not in {c["name"] for c in inspector.get_columns("category_groups")}:
        return "0014"
    if not inspector.has_table("import_jobs"):
        return "0015"
    if "timezone" not in {c["name"] for c in inspector.get_columns("families")}:
        return "0016"
    if not inspector.has_table("merchants"):
        return "0017"
    if not any("UUID" in str(c["type"]).upper() for c in inspector.get_columns("families") if c["name"] == "id"):
        return "0018"
    if "excluded" not in columns:
        return "0019"
    if not inspector.has_table("oauth_grants"):
        return "0020"
    return "0021"


def upgrade_database(url: str = DATABASE_URL, revision: str = "head") -> None:
    """Bring the database at `url` to the latest revision (or to `revision`, which the tests use to stop early).

    Two processes can start at once (two API containers). A lock held for the whole run makes the second
    wait until the first is done, and then find nothing left to do.
    """
    config = alembic_config(url)
    engine = create_engine(url)
    try:
        with engine.connect() as lock_connection:
            lock_connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
            try:
                inspector = inspect(engine)
                if not inspector.has_table("alembic_version"):
                    current = detect_revision(inspector)
                    if current is not None:
                        print(f"Existing database without migration history: recording revision {current}")
                        command.stamp(config, current)
                command.upgrade(config, revision)
            finally:
                lock_connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
                lock_connection.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    upgrade_database()
    print("Database is up to date")

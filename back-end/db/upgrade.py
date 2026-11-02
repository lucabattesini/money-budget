"""Bring the database to the latest schema: `python -m db.upgrade`.

Run by Docker start-up before the API. It is safe to run any number of times.

Databases created before Alembic have no `alembic_version` table. For those, the schema is inspected to
find which of the old hand-written changes it already has, the matching revision is recorded, and only
the missing revisions are applied.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from db.connection import DATABASE_URL

BACK_END = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    config = Config(str(BACK_END / "alembic.ini"))
    config.set_main_option("script_location", str(BACK_END / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # % is special in config values
    return config


def detect_revision(inspector) -> str | None:
    """Which revision a database without alembic_version is already at (None: an empty database)."""
    if not inspector.has_table("transactions"):
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
    return "0005"


def upgrade_database(url: str = DATABASE_URL) -> None:
    config = alembic_config(url)
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            current = detect_revision(inspector)
            if current is not None:
                print(f"Existing database without migration history: recording revision {current}")
                command.stamp(config, current)
    finally:
        engine.dispose()
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade_database()
    print("Database is up to date")

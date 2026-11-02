"""Alembic environment: connects with the app's database URL and compares against the app's models."""

from alembic import context
from sqlalchemy import create_engine

from db.connection import DATABASE_URL, Base
from schemas import tables  # noqa: F401  (importing the models is what registers their tables)

config = context.config
# Tests (and db.upgrade) can point at another database through the config; otherwise DB_URL is used.
url = config.get_main_option("sqlalchemy.url") or DATABASE_URL
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()

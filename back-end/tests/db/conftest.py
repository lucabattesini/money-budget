"""Throwaway Postgres databases for the migration and seeding tests (never the dev or the test one).

Each test gets an empty database named after the test database plus `_migrations_test`, created before
and dropped after.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.conftest import TEST_DB_URL


@pytest.fixture
def url():
    """The URL of an empty scratch database."""
    base = make_url(TEST_DB_URL)
    name = f"{base.database}_migrations_test"
    assert name.endswith("_test")
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    scratch = base.set(database=name)
    yield scratch.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def engine(url):
    engine = create_engine(url)
    yield engine
    engine.dispose()

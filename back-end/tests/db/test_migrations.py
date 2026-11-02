"""The Alembic migrations, run against throwaway Postgres databases (never the dev or the test one).

Each test gets an empty database (see tests/db/conftest.py).
"""

from datetime import datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from db.connection import Base
from db.upgrade import alembic_config, detect_revision, upgrade_database
from schemas import tables  # noqa: F401  (registers the models on Base.metadata)

LATEST = "0005"


def _version(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _forget_history(engine):
    """Make the database look like it was created before Alembic existed."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))


# --- a new database -------------------------------------------------------------------


def test_a_new_database_gets_every_table_and_ends_on_the_latest_revision(url, engine):
    upgrade_database(url)

    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "users",
        "categories",
        "transactions",
        "export_jobs",
    }
    assert _version(engine) == LATEST


def test_the_migrations_build_exactly_what_the_models_describe(url, engine):
    """If a model changes without a migration, this fails (and `alembic revision --autogenerate` shows what is missing)."""
    upgrade_database(url)

    with engine.connect() as conn:
        differences = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)

    assert differences == []


def test_running_the_upgrade_again_changes_nothing(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (google_id, name, email) VALUES ('g', 'Ana', 'a@example.com')"))

    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 1


def test_every_revision_can_be_undone_and_redone(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]

    upgrade_database(url)
    assert _version(engine) == LATEST


# --- databases that existed before Alembic --------------------------------------------------


def _old_database(url, engine, revision):
    """Build a database at `revision`, fill it with data, then forget the migration history."""
    command.upgrade(alembic_config(url), revision)
    return engine


def _seed_users_and_categories(conn):
    conn.execute(text("INSERT INTO users (id, google_id, name, email) VALUES (1, 'g', 'Ana', 'a@example.com')"))
    conn.execute(text("INSERT INTO categories (id, name) VALUES (1, 'Alimentação'), (2, 'Transporte'), (3, 'Outros')"))


def test_an_old_database_with_the_category_as_text_is_upgraded_without_losing_data(url, engine):
    _old_database(url, engine, "0001")
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, date, category) VALUES "
                "(1, 1, 'by id', 1000, '2026-03-01 10:00', '2'),"
                "(2, 1, 'by name', 2000, '2026-03-02 10:00', 'alimentação'),"  # the assistant used to store names
                "(3, 1, 'unknown', 3000, '2026-03-03 10:00', 'Pets'),"
                "(4, 1, 'empty', 4000, '2026-03-04 10:00', NULL),"
                "(5, 1, 'id that does not exist', 5000, '2026-03-05 10:00', '99')"
            )
        )
    _forget_history(engine)

    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT label, value, category_id, type, transactioned_at, created_at, updated_at FROM transactions ORDER BY id"
            )
        ).all()
    assert [(r.label, r.value, r.category_id) for r in rows] == [
        ("by id", 1000, 2),
        ("by name", 2000, 1),
        ("unknown", 3000, 3),  # Outros
        ("empty", 4000, 3),
        ("id that does not exist", 5000, 3),
    ]
    assert all(r.type == "debit" for r in rows)  # they were all expenses
    assert rows[0].transactioned_at == datetime(2026, 3, 1, 10, 0)  # the old `date`
    assert all(r.created_at == r.transactioned_at for r in rows)  # the best guess for when it was saved
    assert all(r.updated_at is None for r in rows)
    assert "category" not in {c["name"] for c in inspect(engine).get_columns("transactions")}


@pytest.mark.parametrize(
    ("revision", "expected_detection"),
    [("0002", "0002"), ("0003", "0003"), ("0004", "0004"), ("0005", "0005")],
)
def test_an_old_database_is_recognised_at_the_revision_it_already_has(url, engine, revision, expected_detection):
    _old_database(url, engine, revision)
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
    _forget_history(engine)

    assert detect_revision(inspect(engine)) == expected_detection
    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 3  # nothing was recreated


def test_a_database_made_from_the_models_without_history_is_adopted_as_it_is(url, engine):
    Base.metadata.create_all(engine)  # what the app used to do
    with engine.begin() as conn:
        _seed_users_and_categories(conn)

    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 3


def test_an_empty_database_has_no_revision_to_detect(engine):
    assert detect_revision(inspect(engine)) is None


# --- two processes at once ------------------------------------------------------------------


def test_two_processes_upgrading_a_new_database_at_the_same_time_both_succeed(url, engine):
    """Two API containers starting together: the second must wait for the first, not crash."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    back_end = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DB_URL": url}
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "db.upgrade"],
            cwd=back_end,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    results = [(p.wait(timeout=120), p.stderr.read()) for p in processes]

    assert [code for code, _ in results] == [0, 0, 0], results
    assert _version(engine) == LATEST

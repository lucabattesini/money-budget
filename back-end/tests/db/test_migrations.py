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

LATEST = "0008"


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
        "families",
        "family_invites",
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
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (family_id, google_id, name, email) VALUES (1, 'g', 'Ana', 'a@example.com')")
        )

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
    """One user and three categories, in whatever shape the database has (users only got a family in 0007)."""
    if "family_id" in {c["name"] for c in inspect(conn).get_columns("users")}:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g', 'Ana', 'a@example.com')")
        )
    else:
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
    [
        ("0002", "0002"),
        ("0003", "0003"),
        ("0004", "0004"),
        ("0005", "0005"),
        ("0006", "0006"),
        ("0007", "0007"),
        ("0008", "0008"),
    ],
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


# --- awkward but possible old databases ------------------------------------------------------


def test_a_row_without_a_date_still_gets_a_created_at(url, engine):
    _old_database(url, engine, "0003")
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, date, category_id) VALUES (1, 1, 'no date', 100, NULL, 1)"
            )
        )
    _forget_history(engine)

    upgrade_database(url)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT created_at FROM transactions")).scalar() is not None


def test_a_half_migrated_database_keeps_its_data(url, engine):
    """Both the old text column and the new foreign key exist (the old script stopped half way)."""
    _old_database(url, engine, "0001")
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(text("ALTER TABLE transactions ADD COLUMN category_id INTEGER REFERENCES categories(id)"))
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, date, category) VALUES (1, 1, 'x', 100, '2026-01-01', '2')"
            )
        )
    _forget_history(engine)

    upgrade_database(url)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT category_id FROM transactions")).scalar() == 2
    assert _version(engine) == LATEST


def test_a_hand_edited_database_that_already_has_later_columns_is_not_broken_by_the_upgrade(url, engine):
    """Recorded as the first revision, but `type` and the new dates already exist: the upgrade must cope."""
    _old_database(url, engine, "0004")
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, transactioned_at, category_id, type) VALUES (1, 1, 'x', 100, '2026-01-01', 1, 'credit')"
            )
        )
        conn.execute(text("UPDATE alembic_version SET version_num = '0001'"))

    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        assert conn.execute(text("SELECT type FROM transactions")).scalar() == "credit"  # untouched


def test_the_upgrade_refuses_to_drop_a_category_text_it_cannot_place(url, engine):
    _old_database(url, engine, "0001")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, google_id, name, email) VALUES (1, 'g', 'Ana', 'a@example.com')"))
        conn.execute(text("INSERT INTO categories (id, name) VALUES (1, 'Alimentação')"))  # no 'Outros'
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, date, category) VALUES (1, 1, 'x', 100, '2026-01-01', 'Pets')"
            )
        )
    _forget_history(engine)

    with pytest.raises(RuntimeError, match="Pets"):
        upgrade_database(url)

    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    assert "category" in columns  # the text was not thrown away
    assert _version(engine) == "0001"  # and the failed step was rolled back


def test_a_database_with_only_some_tables_is_reported_not_guessed(url, engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id SERIAL PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="no 'transactions' table"):
        upgrade_database(url)


# --- more of what a real upgrade touches ----------------------------------------------------------


def test_defaults_also_match_the_models(url, engine):
    """A missing or different server default (type = 'debit', created_at = now()) would otherwise go unnoticed."""
    upgrade_database(url)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_the_alembic_command_line_works_as_documented(url):
    """`alembic current` / `alembic check` read the database from DB_URL, like the app does."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    back_end = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DB_URL": url}
    upgrade_database(url)

    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"], cwd=back_end, env=env, capture_output=True, text=True
    )
    check = subprocess.run(
        [sys.executable, "-m", "alembic", "check"], cwd=back_end, env=env, capture_output=True, text=True
    )

    assert LATEST in current.stdout, current.stderr
    assert check.returncode == 0, check.stderr  # the models and the migrations agree


def test_a_password_with_special_characters_does_not_break_the_upgrade(url, engine):
    """Uses its own throwaway role, so the real database user and its password are never touched."""
    from sqlalchemy.engine import make_url

    database = make_url(url).database
    with engine.begin() as conn:
        conn.execute(text("CREATE ROLE migrations_password_test LOGIN PASSWORD 'p%ss:w@rd/1'"))
        conn.execute(text(f'ALTER DATABASE "{database}" OWNER TO migrations_password_test'))
    try:
        special = make_url(url).set(username="migrations_password_test", password="p%ss:w@rd/1")

        upgrade_database(special.render_as_string(hide_password=False))

        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == LATEST
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'ALTER DATABASE "{database}" OWNER TO money'))
            conn.execute(text("DROP OWNED BY migrations_password_test"))
            conn.execute(text("DROP ROLE migrations_password_test"))


def test_undoing_the_revisions_on_a_database_with_data_drops_only_what_the_old_schema_cannot_hold(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value, type, transactioned_at, category_id) "
                "VALUES (1, 1, 1, 'salário', 5000, 'credit', '2026-03-01 10:00', 1)"
            )
        )

    command.downgrade(alembic_config(url), "0002")

    with engine.connect() as conn:
        row = conn.execute(text("SELECT label, value, date, category_id FROM transactions")).one()
    assert (row.label, row.value, row.date, row.category_id) == ("salário", 5000, datetime(2026, 3, 1, 10, 0), 1)
    columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
    assert not columns & {"type", "created_at", "updated_at", "transactioned_at"}  # these did not exist then


def test_a_large_old_table_is_upgraded_with_a_handful_of_statements(url, engine):
    """One statement per distinct category text, not one per row (it used to be one per row)."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    _old_database(url, engine, "0001")
    with engine.begin() as conn:
        _seed_users_and_categories(conn)
        conn.execute(
            text(
                "INSERT INTO transactions (user_id, label, value, date, category) "
                "SELECT 1, 'row ' || n, n, '2026-01-01', (ARRAY['1', 'transporte', 'Pets', ' 2 ', ''])[1 + n % 5] "
                "FROM generate_series(1, 5000) AS n"
            )
        )
    _forget_history(engine)
    updates = []

    def count(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("UPDATE TRANSACTIONS SET CATEGORY_ID"):
            updates.append(statement)

    event.listen(Engine, "before_cursor_execute", count)
    try:
        upgrade_database(url)
    finally:
        event.remove(Engine, "before_cursor_execute", count)

    assert len(updates) <= 10, f"{len(updates)} category updates for 5000 rows"
    with engine.connect() as conn:
        counts = dict(conn.execute(text("SELECT category_id, count(*) FROM transactions GROUP BY category_id")).all())
        unmapped = conn.execute(text("SELECT count(*) FROM transactions WHERE category_id IS NULL")).scalar()
    # '1' -> 1, 'transporte' and ' 2 ' -> 2, 'Pets' (unknown) and '' -> Outros (3)
    assert counts == {1: 1000, 2: 2000, 3: 2000}
    assert unmapped == 0


def test_duplicate_and_badly_formatted_phone_numbers_are_cleaned_before_the_number_becomes_unique(url, engine):
    command.upgrade(alembic_config(url), "0005")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_id, name, email, whatsapp_phone) VALUES "
                "(1, 'g1', 'Ana', 'a@example.com', '+55 (11) 99999-0000'),"
                "(2, 'g2', 'Bia', 'b@example.com', '5511999990000'),"  # same number as Ana once cleaned
                "(3, 'g3', 'Caio', 'c@example.com', '5522888880000'),"
                "(4, 'g4', 'Dani', 'd@example.com', '--'),"  # no digits at all
                "(5, 'g5', 'Edu', 'e@example.com', NULL),"
                "(6, 'g6', 'Fabi', 'f@example.com', NULL)"  # several users without a number are fine
            )
        )

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        phones = dict(conn.execute(text("SELECT id, whatsapp_phone FROM users ORDER BY id")).all())
    assert phones == {1: "5511999990000", 2: None, 3: "5522888880000", 4: None, 5: None, 6: None}


# --- 0007: ownership moves from the user to the family ----------------------------------------


def _database_before_families(url, engine):
    """Two users who each own data, a default category, and a transaction nobody owns."""
    command.upgrade(alembic_config(url), "0006")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_id, name, email) VALUES "
                "(1, 'g1', 'Ana', 'a@example.com'), (2, 'g2', 'Bia', 'b@example.com')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, user_id, name) VALUES "
                "(1, NULL, 'Outros'), (2, 1, 'Pets da Ana'), (3, 2, 'Plantas da Bia')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (id, user_id, label, value, type, transactioned_at, category_id) VALUES "
                "(1, 1, 'ana 1', 100, 'debit', '2026-01-01', 1), (2, 1, 'ana 2', 200, 'credit', '2026-01-02', 2),"
                "(3, 2, 'bia 1', 300, 'debit', '2026-01-03', 3), (4, NULL, 'nobody', 400, 'debit', '2026-01-04', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO export_jobs (id, user_id, format, status) VALUES (1, 1, 'csv', 'done'), (2, 2, 'xlsx', 'queued')"
            )
        )


def test_every_existing_user_gets_a_family_of_their_own(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        families = dict(conn.execute(text("SELECT id, family_id FROM users")).all())
        assert conn.execute(text("SELECT count(*) FROM families")).scalar() == 2
    assert families[1] != families[2]


def test_data_follows_its_owner_into_the_family_and_keeps_who_created_it(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        family = dict(conn.execute(text("SELECT id, family_id FROM users")).all())
        transactions = {r.id: (r.family_id, r.user_id) for r in conn.execute(text("SELECT * FROM transactions"))}
        categories = {r.id: r.family_id for r in conn.execute(text("SELECT * FROM categories"))}
        jobs = {r.id: (r.family_id, r.requested_by) for r in conn.execute(text("SELECT * FROM export_jobs"))}
    assert transactions[1] == (family[1], 1)
    assert transactions[2] == (family[1], 1)
    assert transactions[3] == (family[2], 2)  # nothing of Bia's ended up with Ana
    assert categories == {1: None, 2: family[1], 3: family[2]}  # the default category stays shared
    assert jobs == {1: (family[1], 1), 2: (family[2], 2)}


def test_a_transaction_nobody_owned_is_dropped_and_everything_else_is_kept(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        assert sorted(conn.execute(text("SELECT label FROM transactions")).scalars()) == ["ana 1", "ana 2", "bia 1"]


def test_the_old_user_columns_are_gone_except_the_authors_of_transactions(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), "head")

    for table in ("categories", "export_jobs"):  # transactions keep it: it says who entered the row
        assert "user_id" not in {c["name"] for c in inspect(engine).get_columns(table)}
    columns = {c["name"]: c for c in inspect(engine).get_columns("transactions")}
    assert "user_id" in columns and columns["user_id"]["nullable"] is False


def test_undoing_the_family_revision_gives_every_row_its_user_back(url, engine):
    _database_before_families(url, engine)
    command.upgrade(alembic_config(url), "head")

    command.downgrade(alembic_config(url), "0006")

    with engine.connect() as conn:
        transactions = dict(conn.execute(text("SELECT id, user_id FROM transactions")).all())
        categories = dict(conn.execute(text("SELECT id, user_id FROM categories")).all())
        jobs = dict(conn.execute(text("SELECT id, user_id FROM export_jobs")).all())
    assert transactions == {1: 1, 2: 1, 3: 2}
    assert categories == {1: None, 2: 1, 3: 2}
    assert jobs == {1: 1, 2: 2}
    assert "families" not in inspect(engine).get_table_names()


def test_a_transaction_that_used_another_persons_category_loses_it_instead_of_showing_it_to_the_wrong_family(
    url, engine
):
    _database_before_families(url, engine)
    with engine.begin() as conn:  # Ana's transaction 1 now points at Bia's private category (3)
        conn.execute(text("UPDATE transactions SET category_id = 3 WHERE id = 1"))

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        categories = dict(conn.execute(text("SELECT id, category_id FROM transactions")).all())
    assert categories[1] is None  # was Bia's private category
    assert categories[2] is not None  # Ana's own category is kept
    assert categories[3] == 3  # Bia's own is kept


# --- 0008: roles and invite codes ------------------------------------------------------------


def test_everyone_who_exists_becomes_the_owner_of_their_own_family(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT role FROM users ORDER BY id")).scalars().all() == ["owner", "owner"]
        assert conn.execute(text("SELECT count(*) FROM family_invites")).scalar() == 0


def test_undoing_the_invites_revision_removes_roles_and_codes_and_keeps_the_families(url, engine):
    _database_before_families(url, engine)
    command.upgrade(alembic_config(url), "head")

    command.downgrade(alembic_config(url), "0007")

    assert "family_invites" not in inspect(engine).get_table_names()
    assert "role" not in {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM families")).scalar() == 2

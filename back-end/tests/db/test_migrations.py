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

LATEST = "0024"
BEFORE_CONNECTOR = "0020"
BEFORE_INDEX = "0021"
BEFORE_UUIDS = "0018"  # the migrations of the older tests below end here: ids were still counting numbers


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
        "category_groups",
        "users",
        "categories",
        "transactions",
        "export_jobs",
        "budgets",
        "import_jobs",
        "merchants",
        "oauth_clients",
        "oauth_codes",
        "oauth_grants",
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
        conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid())"))
        conn.execute(
            text(
                "INSERT INTO users (id, family_id, google_id, name, email) "
                "SELECT gen_random_uuid(), id, 'g', 'Ana', 'a@example.com' FROM families"
            )
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
    if "group_id" in {c["name"] for c in inspect(conn).get_columns("categories")}:  # groups came with 0010
        has_position = "position" in {c["name"] for c in inspect(conn).get_columns("category_groups")}  # came with 0015
        conn.execute(
            text(
                "INSERT INTO category_groups (name, position) VALUES ('Outros', 1) ON CONFLICT (name) DO NOTHING"
                if has_position
                else "INSERT INTO category_groups (name) VALUES ('Outros') ON CONFLICT (name) DO NOTHING"
            )
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, name, group_id) SELECT v.id, v.name, g.id "
                "FROM (VALUES (1, 'Alimentação'), (2, 'Transporte'), (3, 'Outros')) AS v(id, name), category_groups g "
                "WHERE g.name = 'Outros'"
            )
        )
    else:
        conn.execute(
            text("INSERT INTO categories (id, name) VALUES (1, 'Alimentação'), (2, 'Transporte'), (3, 'Outros')")
        )


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

    upgrade_database(url, BEFORE_UUIDS)

    assert _version(engine) == BEFORE_UUIDS
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
        ("0009", "0009"),
        ("0010", "0010"),
        ("0011", "0010"),  # only names changed: the schema looks like 0010, and running 0011 again changes nothing
        ("0012", "0010"),  # likewise: only the default categories changed
        ("0013", "0013"),
        ("0014", "0014"),
        ("0015", "0015"),
        ("0016", "0016"),
        ("0017", "0017"),
        ("0018", "0018"),
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
        conn.execute(text("INSERT INTO category_groups (id, name, position) VALUES (gen_random_uuid(), 'Outros', 1)"))
        conn.execute(
            text(
                "INSERT INTO categories (id, name, group_id) SELECT gen_random_uuid(), v.name, g.id "
                "FROM (VALUES ('Alimentação'), ('Transporte'), ('Outros')) AS v(name), category_groups g"
            )
        )

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

    upgrade_database(url, BEFORE_UUIDS)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT category_id FROM transactions")).scalar() == 2
    assert _version(engine) == BEFORE_UUIDS


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
    command.upgrade(alembic_config(url), BEFORE_UUIDS)
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
        upgrade_database(url, BEFORE_UUIDS)
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

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

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

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        families = dict(conn.execute(text("SELECT id, family_id FROM users")).all())
        assert conn.execute(text("SELECT count(*) FROM families")).scalar() == 2
    assert families[1] != families[2]


def test_data_follows_its_owner_into_the_family_and_keeps_who_created_it(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

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

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        assert sorted(conn.execute(text("SELECT label FROM transactions")).scalars()) == ["ana 1", "ana 2", "bia 1"]


def test_the_old_user_columns_are_gone_except_the_authors_of_transactions(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    for table in ("categories", "export_jobs"):  # transactions keep it: it says who entered the row
        assert "user_id" not in {c["name"] for c in inspect(engine).get_columns(table)}
    columns = {c["name"]: c for c in inspect(engine).get_columns("transactions")}
    assert "user_id" in columns and columns["user_id"]["nullable"] is False


def test_undoing_the_family_revision_gives_every_row_its_user_back(url, engine):
    _database_before_families(url, engine)
    command.upgrade(alembic_config(url), BEFORE_UUIDS)

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

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        categories = dict(conn.execute(text("SELECT id, category_id FROM transactions")).all())
    assert categories[1] is None  # was Bia's private category
    assert categories[2] is not None  # Ana's own category is kept
    assert categories[3] == 3  # Bia's own is kept


# --- 0008: roles and invite codes ------------------------------------------------------------


def test_everyone_who_exists_becomes_the_owner_of_their_own_family(url, engine):
    _database_before_families(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT role FROM users ORDER BY id")).scalars().all() == ["owner", "owner"]
        assert conn.execute(text("SELECT count(*) FROM family_invites")).scalar() == 0


def test_undoing_the_invites_revision_removes_roles_and_codes_and_keeps_the_families(url, engine):
    _database_before_families(url, engine)
    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    command.downgrade(alembic_config(url), "0007")

    assert "family_invites" not in inspect(engine).get_table_names()
    assert "role" not in {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM families")).scalar() == 2


# --- 0009: families kept for 30 days after their last person left ---------------------------------


def test_a_family_that_is_already_empty_is_marked_abandoned_and_the_others_are_not(url, engine):
    command.upgrade(alembic_config(url), "0008")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1), (2)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g', 'Ana', 'a@e.com')")
        )

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        abandoned = dict(conn.execute(text("SELECT id, abandoned_at IS NOT NULL FROM families")).all())
        assert conn.execute(text("SELECT previous_family_id FROM users")).scalar() is None
    assert abandoned == {1: False, 2: True}  # family 2 has nobody, so its 30 days start now


def test_undoing_the_abandoned_families_revision_drops_only_its_columns(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0008")

    assert "abandoned_at" not in {c["name"] for c in inspect(engine).get_columns("families")}
    assert "previous_family_id" not in {c["name"] for c in inspect(engine).get_columns("users")}


# --- 0010: category groups -----------------------------------------------------------------------------


def _database_before_groups(url, engine):
    command.upgrade(alembic_config(url), "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g', 'Ana', 'a@e.com')")
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, family_id, name) VALUES "
                "(1, NULL, 'Aluguel'), (2, NULL, 'Supermercado'), (3, NULL, 'investimentos'), (4, NULL, 'Outros'),"
                "(5, NULL, 'Uma que a lista não conhece'), (6, 1, 'Plantas da família'), (7, 1, 'Aluguel')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value, category_id) "
                "VALUES (1, 1, 1, 'x', 100, 1)"
            )
        )


def _groups_of_categories(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT c.id, g.name FROM categories c JOIN category_groups g ON g.id = c.group_id ORDER BY c.id")
        ).all()
    return dict(rows)


def test_the_twelve_groups_exist_after_the_migration_with_outros_last(url, engine):
    command.upgrade(alembic_config(url), "0010")

    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM category_groups ORDER BY id")).scalars().all()
    assert names == [
        "Casa",
        "Alimentação",
        "Transporte",
        "Saúde e bem-estar",
        "Lazer",
        "Educação",
        "Compras e presentes",
        "Finanças",
        "Receitas",
        "Transferências",
        "Investimentos",
        "Outros",
    ]


def test_existing_default_categories_are_grouped_by_name_and_the_rest_goes_to_outros(url, engine):
    _database_before_groups(url, engine)

    command.upgrade(alembic_config(url), "0010")

    assert _groups_of_categories(engine) == {
        1: "Casa",
        2: "Alimentação",
        3: "Investimentos",  # the match ignores case
        4: "Outros",
        5: "Outros",  # a default category the list does not know
        6: "Outros",  # a family's own category
        7: "Outros",  # a family's "Aluguel" is not the default one, so it is not grouped as one
    }


def test_the_migration_keeps_every_category_and_what_points_to_it(url, engine):
    _database_before_groups(url, engine)

    command.upgrade(alembic_config(url), "0010")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 7
        assert conn.execute(text("SELECT category_id FROM transactions")).scalar() == 1


def test_every_category_must_have_a_group(url, engine):
    upgrade_database(url)

    with engine.begin() as conn:
        with pytest.raises(Exception, match="group_id"):
            conn.execute(text("INSERT INTO categories (id, name) VALUES (gen_random_uuid(), 'sem grupo')"))


def test_undoing_the_groups_revision_drops_the_groups_and_keeps_the_categories(url, engine):
    _database_before_groups(url, engine)
    command.upgrade(alembic_config(url), "0010")

    command.downgrade(alembic_config(url), "0009")

    assert "category_groups" not in inspect(engine).get_table_names()
    assert "group_id" not in {c["name"] for c in inspect(engine).get_columns("categories")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 7


# --- 0011: emojis in the names of the default categories ------------------------------------------------


def _database_before_emojis(url, engine):
    command.upgrade(alembic_config(url), "0010")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g', 'Ana', 'a@e.com')")
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, family_id, name, group_id) "
                "SELECT v.id, v.family_id, v.name, g.id FROM (VALUES "
                "(1, NULL, 'Supermercado'), (2, NULL, 'alimentação'), (3, NULL, '🛒 Compras'), (4, NULL, 'Uma desconhecida'),"
                "(5, 1, 'Supermercado'), (6, 1, 'Plantas')) AS v(id, family_id, name), category_groups g "
                "WHERE g.name = 'Outros'"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value, category_id) VALUES (1, 1, 1, 'x', 100, 1)"
            )
        )


def _names(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, name FROM categories ORDER BY id")).all())


def test_default_categories_get_their_emoji_in_front_of_the_name(url, engine):
    _database_before_emojis(url, engine)

    command.upgrade(alembic_config(url), "0011")

    names = _names(engine)
    assert names[1] == "🛒 Supermercado"
    assert names[2] == "🍽️ alimentação"  # found ignoring case; the words are kept as they were stored


def test_a_family_category_an_emoji_already_there_and_unknown_names_are_left_alone(url, engine):
    _database_before_emojis(url, engine)

    command.upgrade(alembic_config(url), "0011")

    names = _names(engine)
    assert names[3] == "🛒 Compras"  # not given a second emoji
    assert names[4] == "Uma desconhecida"
    assert (names[5], names[6]) == ("Supermercado", "Plantas")  # a family's own, even when the name matches a default


def test_the_emojis_change_no_id_and_no_transaction(url, engine):
    _database_before_emojis(url, engine)

    command.upgrade(alembic_config(url), "0011")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT category_id FROM transactions")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 6


def test_undoing_the_emojis_gives_the_default_categories_their_old_names_back(url, engine):
    _database_before_emojis(url, engine)
    command.upgrade(alembic_config(url), "0011")

    command.downgrade(alembic_config(url), "0010")

    names = _names(engine)
    assert names[1] == "Supermercado"
    assert names[3] == "Compras"  # any emoji of the list in front of a default name is removed, even another one
    assert (names[5], names[6]) == ("Supermercado", "Plantas")


# --- 0012: the default categories of Monarch Money -------------------------------------------------------------


def _database_before_monarch(url, engine):
    command.upgrade(alembic_config(url), "0011")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g', 'Ana', 'a@e.com')")
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, family_id, name, group_id) "
                "SELECT v.id, v.family_id, v.name, g.id FROM (VALUES "
                "(1, NULL, '🎨 Hobbies', 'Lazer'), (2, NULL, '📺 Assinaturas', 'Lazer'), (3, NULL, '🎬 Entretenimento', 'Lazer'),"
                "(4, NULL, '🍽️ Alimentação', 'Alimentação'), (5, NULL, '🏠 Aluguel', 'Casa'),"
                "(6, NULL, 'Uma que a lista não conhece', 'Outros'), (7, NULL, '🪙 Criptomoedas', 'Investimentos'),"
                "(8, 1, 'Plantas', 'Casa'), (9, 1, 'Bolsa de valores', 'Investimentos'), (10, 1, 'Hobbies', 'Lazer')"
                ") AS v(id, family_id, name, grp), category_groups g WHERE g.name = v.grp"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value, category_id) VALUES "
                "(1, 1, 1, 'a', 100, 1), (2, 1, 1, 'b', 200, 2), (3, 1, 1, 'c', 300, 3), (4, 1, 1, 'd', 400, 4)"
            )
        )


def _category_rows(engine):
    with engine.connect() as conn:
        return {
            row.id: (row.name, row.family_id, row.group)
            for row in conn.execute(
                text(
                    'SELECT c.id, c.name, c.family_id, g.name AS "group" '
                    "FROM categories c JOIN category_groups g ON g.id = c.group_id"
                )
            )
        }


def test_the_monarch_groups_replace_the_old_ones_in_order(url, engine):
    command.upgrade(alembic_config(url), "0022")  # before the groups were put in order of priority

    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM category_groups ORDER BY position")).scalars().all()
    assert names == [
        "Receitas",
        "Presentes e Doações",
        "Auto e Transporte",
        "Moradia",
        "Contas e Serviços",
        "Alimentação",
        "Compras",
        "Viagem e Estilo de Vida",
        "Filhos",
        "Educação",
        "Saúde e Bem-estar",
        "Finanças",
        "Outros",
        "Transferências",
    ]


def test_old_default_categories_become_the_closest_monarch_one_and_several_are_merged_into_one(url, engine):
    _database_before_monarch(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    rows = _category_rows(engine)
    # Hobbies, Assinaturas and Entretenimento are one category now: the first row is kept, the others are gone
    assert rows[1] == ("🎬 Entretenimento e Lazer", None, "Viagem e Estilo de Vida")
    assert 2 not in rows and 3 not in rows
    assert rows[4] == ("🍽️ Restaurantes e Bares", None, "Alimentação")
    assert rows[5] == ("🏠 Aluguel", None, "Moradia")
    assert rows[7] == ("🔄 Transferência", None, "Transferências")  # investments are transfers


def test_a_default_category_the_old_list_did_not_know_keeps_its_name_in_outros(url, engine):
    _database_before_monarch(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    assert _category_rows(engine)[6] == ("Uma que a lista não conhece", None, "Outros")


def test_the_transactions_of_merged_categories_follow_to_the_one_that_is_kept(url, engine):
    _database_before_monarch(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        categories = dict(conn.execute(text("SELECT id, category_id FROM transactions ORDER BY id")).all())
        assert conn.execute(text("SELECT count(*) FROM transactions")).scalar() == 4
    assert categories == {1: 1, 2: 1, 3: 1, 4: 4}


def test_a_familys_own_categories_are_not_renamed_and_move_to_the_group_that_replaces_theirs(url, engine):
    _database_before_monarch(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    rows = _category_rows(engine)
    assert rows[8] == ("Plantas", 1, "Moradia")  # Casa
    assert rows[9] == ("Bolsa de valores", 1, "Transferências")  # Investimentos
    assert rows[10] == ("Hobbies", 1, "Viagem e Estilo de Vida")  # not merged with the default Hobbies


def test_no_old_group_is_left_behind(url, engine):
    _database_before_monarch(url, engine)

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM category_groups")).scalar() == 14
        assert conn.execute(text("SELECT count(*) FROM category_groups WHERE name LIKE '\\_\\_%'")).scalar() == 0


def test_undoing_the_monarch_revision_brings_back_the_old_groups_and_names_and_keeps_every_row(url, engine):
    _database_before_monarch(url, engine)
    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    command.downgrade(alembic_config(url), "0011")

    rows = _category_rows(engine)
    assert rows[1] == ("🎬 Entretenimento", None, "Lazer")  # the merged ones cannot be told apart again
    assert rows[4] == ("🍽️ Alimentação", None, "Alimentação")
    assert rows[8] == ("Plantas", 1, "Casa")
    assert rows[9] == ("Bolsa de valores", 1, "Transferências")
    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM category_groups ORDER BY id")).scalars().all()
        assert conn.execute(text("SELECT category_id FROM transactions WHERE id = 4")).scalar() == 4
    assert names[0] == "Casa" and len(names) == 12


def test_a_default_category_that_already_has_a_new_name_is_put_in_its_new_group(url, engine):
    """Someone may have created a default such as "Telefone" by hand: it must not stay in "Outros", where the seed
    would then never create the proper one."""
    command.upgrade(alembic_config(url), "0011")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO categories (id, name, group_id) "
                "SELECT 1, 'telefone', id FROM category_groups WHERE name = 'Outros'"
            )
        )

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    assert _category_rows(engine)[1] == ("📱 Telefone", None, "Contas e Serviços")


# --- 0013: the currency and the language of a family -------------------------------------------------------


def test_existing_families_keep_seeing_reais_in_portuguese(url, engine):
    command.upgrade(alembic_config(url), "0012")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1), (2)"))

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT currency, language FROM families ORDER BY id")).all()
    assert rows == [("BRL", "pt"), ("BRL", "pt")]


def test_undoing_the_currency_and_language_revision_drops_only_those_columns(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0012")

    columns = {c["name"] for c in inspect(engine).get_columns("families")}
    assert "currency" not in columns and "language" not in columns
    assert {"id", "created_at", "abandoned_at"} <= columns


# --- 0014: monthly budgets ---------------------------------------------------------------------------------


def test_the_budgets_table_allows_one_amount_per_family_category_and_month(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:
        family = conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid()) RETURNING id")).scalar()
        category = conn.execute(
            text(
                "INSERT INTO categories (id, name, group_id) SELECT gen_random_uuid(), 'x', id "
                "FROM category_groups LIMIT 1 RETURNING id"
            )
        ).scalar()
    insert = text(
        "INSERT INTO budgets (id, family_id, category_id, month, amount) "
        "VALUES (gen_random_uuid(), :family, :category, :month, :amount)"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"family": family, "category": category, "month": "2026-11-01", "amount": 100})
        conn.execute(insert, {"family": family, "category": category, "month": "2026-12-01", "amount": 100})

    with engine.begin() as conn:
        with pytest.raises(Exception, match="uq_budgets_family_category_month"):
            conn.execute(insert, {"family": family, "category": category, "month": "2026-11-01", "amount": 200})


def test_undoing_the_budgets_revision_drops_only_the_budgets(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0013")

    assert "budgets" not in inspect(engine).get_table_names()
    assert {"families", "categories", "transactions"} <= set(inspect(engine).get_table_names())


# --- 0015: the order of the category groups ----------------------------------------------------------------


def test_the_groups_keep_the_order_they_had_and_get_a_position(url, engine):
    command.upgrade(alembic_config(url), "0014")
    with engine.connect() as conn:
        before = conn.execute(text("SELECT name FROM category_groups ORDER BY id")).scalars().all()

    command.upgrade(alembic_config(url), BEFORE_UUIDS)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, position FROM category_groups ORDER BY position")).all()
    assert [name for name, _ in rows] == before
    assert [position for _, position in rows] == list(range(1, len(before) + 1))


def test_every_group_must_have_a_position(url, engine):
    upgrade_database(url)

    with engine.begin() as conn:
        with pytest.raises(Exception, match="position"):
            conn.execute(text("INSERT INTO category_groups (name) VALUES ('sem posição')"))


def test_undoing_the_position_revision_drops_only_the_column(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0014")

    assert "position" not in {c["name"] for c in inspect(engine).get_columns("category_groups")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM category_groups")).scalar() == 14


# --- 0016: importing transactions in steps ------------------------------------------------------------------------------


def test_undoing_the_import_revision_drops_only_its_table(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0015")

    names = set(inspect(engine).get_table_names())
    assert "import_jobs" not in names
    assert {"export_jobs", "transactions", "budgets"} <= names


# --- 0017: the timezone of a family (TKT-65) -----------------------------------------------------------------------------


def test_existing_families_get_brasilia_time_and_keep_their_transactions(url, engine):
    upgrade_database(url)
    command.downgrade(alembic_config(url), "0016")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1), (2)"))

    command.upgrade(alembic_config(url), "0017")

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, timezone FROM families ORDER BY id")).all()
    assert rows == [(1, "America/Sao_Paulo"), (2, "America/Sao_Paulo")]


def test_undoing_the_timezone_revision_drops_only_that_column(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0016")

    columns = {c["name"] for c in inspect(engine).get_columns("families")}
    assert "timezone" not in columns
    assert {"currency", "language"} <= columns


# --- 0018: merchants (TKT-58) --------------------------------------------------------------------------------------------


def test_existing_families_have_merchants_off_and_existing_transactions_none(url, engine):
    upgrade_database(url)
    command.downgrade(alembic_config(url), "0017")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO users (id, family_id, google_id, name, email) VALUES (1, 1, 'g1', 'Ana', 'a@x.com')")
        )
        conn.execute(text("INSERT INTO transactions (family_id, user_id, label, value) VALUES (1, 1, 'a', 10)"))

    command.upgrade(alembic_config(url), "0018")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT merchants_enabled FROM families")).scalar() is False
        assert conn.execute(text("SELECT merchant_id FROM transactions")).scalar() is None
        assert conn.execute(text("SELECT count(*) FROM merchants")).scalar() == 0


def test_undoing_the_merchants_revision_drops_only_what_it_added(url, engine):
    upgrade_database(url)

    command.downgrade(alembic_config(url), "0017")

    assert "merchants" not in inspect(engine).get_table_names()
    assert "merchant_id" not in {c["name"] for c in inspect(engine).get_columns("transactions")}
    assert "merchants_enabled" not in {c["name"] for c in inspect(engine).get_columns("families")}
    assert "timezone" in {c["name"] for c in inspect(engine).get_columns("families")}


# --- 0019: UUID identifiers (TKT-74) -----------------------------------------------------------


def _data_with_every_kind_of_link(engine):
    """Rows with counting-number ids that point at one another through every foreign key, at revision 0018."""
    with engine.begin() as conn:
        group = conn.execute(text("SELECT id FROM category_groups ORDER BY position LIMIT 1")).scalar()
        conn.execute(text("INSERT INTO families (id) VALUES (10), (20)"))
        conn.execute(
            text(
                "INSERT INTO users (id, family_id, previous_family_id, role, google_id, name, email) VALUES "
                "(1, 10, NULL, 'owner', 'g1', 'Ana', 'a@e.com'), (2, 10, NULL, 'member', 'g2', 'Bia', 'b@e.com'),"
                "(3, 20, 10, 'owner', 'g3', 'Caio', 'c@e.com')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO categories (id, family_id, name, group_id) VALUES (500, 10, 'Plantas', :g), (501, NULL, 'Geral', :g)"
            ),
            {"g": group},
        )
        conn.execute(text("INSERT INTO merchants (id, family_id, name) VALUES (70, 10, 'Uber')"))
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value, category_id, merchant_id) VALUES "
                "(900, 10, 1, 'with everything', 100, 500, 70), (901, 10, 2, 'default category', 200, 501, NULL),"
                "(902, 10, 1, 'no category', 300, NULL, NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO budgets (id, family_id, category_id, month, amount) VALUES (5, 10, 500, '2026-11-01', 1000)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO family_invites (id, family_id, created_by, used_by, code_hash, code_hint, expires_at) VALUES "
                "(8, 10, 1, 2, 'h1', '1111', now()), (9, 10, 1, NULL, 'h2', '2222', now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO export_jobs (id, family_id, requested_by, format, status) VALUES (3, 10, 2, 'csv', 'done')"
            )
        )
        conn.execute(text("INSERT INTO import_jobs (id, family_id, requested_by, status) VALUES (4, 10, 1, 'staged')"))
    return group


def _links(conn):
    """What points at what, written with the labels and names that do not change when the ids do."""
    return {
        "transactions": conn.execute(
            text(
                "SELECT t.label, u.name, f.id IS NOT NULL AS has_family, c.name, m.name FROM transactions t "
                "JOIN users u ON u.id = t.user_id JOIN families f ON f.id = t.family_id "
                "LEFT JOIN categories c ON c.id = t.category_id LEFT JOIN merchants m ON m.id = t.merchant_id "
                "WHERE f.id = u.family_id ORDER BY t.label"
            )
        ).all(),
        "budget": conn.execute(
            text("SELECT c.name, b.amount FROM budgets b JOIN categories c ON c.id = b.category_id")
        ).all(),
        "invites": conn.execute(
            text(
                "SELECT i.code_hint, a.name, u.name FROM family_invites i JOIN users a ON a.id = i.created_by "
                "LEFT JOIN users u ON u.id = i.used_by ORDER BY i.code_hint"
            )
        ).all(),
        "export": conn.execute(text("SELECT u.name FROM export_jobs e JOIN users u ON u.id = e.requested_by")).all(),
        "left_family": conn.execute(
            text(
                "SELECT u.name, (SELECT count(*) FROM users o WHERE o.family_id = u.previous_family_id) FROM users u "
                "WHERE u.previous_family_id IS NOT NULL"
            )
        ).all(),
        "default_category": conn.execute(text("SELECT family_id FROM categories WHERE name = 'Geral'")).scalar(),
        "category_group": conn.execute(
            text("SELECT count(*) FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).scalar(),
        "family_of": conn.execute(
            text(
                "SELECT u.name, count(*) FROM users u JOIN users o ON o.family_id = u.family_id GROUP BY u.name ORDER BY u.name"
            )
        ).all(),
    }


def test_the_uuid_revision_gives_every_row_a_uuid_and_keeps_every_link(url, engine):
    command.upgrade(alembic_config(url), BEFORE_UUIDS)
    _data_with_every_kind_of_link(engine)
    with engine.connect() as conn:
        before = _links(conn)

    upgrade_database(url)

    assert _version(engine) == LATEST
    with engine.connect() as conn:
        assert _links(conn) == before
        for table in (
            "families",
            "users",
            "categories",
            "category_groups",
            "transactions",
            "merchants",
            "budgets",
            "family_invites",
            "export_jobs",
        ):
            assert str(conn.execute(text(f"SELECT pg_typeof(id) FROM {table} LIMIT 1")).scalar()) == "uuid", table
        assert conn.execute(text("SELECT count(DISTINCT id) FROM transactions")).scalar() == 3  # not one id for all
        # The links are real foreign keys again: a transaction cannot point at a category that is not there
    with engine.begin() as conn, pytest.raises(Exception, match="transactions_category_id_fkey"):
        conn.execute(text("UPDATE transactions SET category_id = gen_random_uuid()"))


def test_the_uuid_revision_drops_imports_in_progress_because_their_saved_rows_hold_old_ids(url, engine):
    command.upgrade(alembic_config(url), BEFORE_UUIDS)
    _data_with_every_kind_of_link(engine)

    upgrade_database(url)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM import_jobs")).scalar() == 0


def test_the_budgets_rule_of_one_amount_per_family_category_and_month_survives_the_uuid_revision(url, engine):
    command.upgrade(alembic_config(url), BEFORE_UUIDS)
    _data_with_every_kind_of_link(engine)
    upgrade_database(url)

    with engine.begin() as conn, pytest.raises(Exception, match="uq_budgets_family_category_month"):
        conn.execute(
            text(
                "INSERT INTO budgets (id, family_id, category_id, month, amount) "
                "SELECT gen_random_uuid(), family_id, category_id, month, 5 FROM budgets"
            )
        )


def test_undoing_the_uuid_revision_gives_counting_numbers_back_and_keeps_every_link(url, engine):
    command.upgrade(alembic_config(url), BEFORE_UUIDS)
    _data_with_every_kind_of_link(engine)
    upgrade_database(url)
    with engine.connect() as conn:
        before = _links(conn)

    command.downgrade(alembic_config(url), BEFORE_UUIDS)

    assert _version(engine) == BEFORE_UUIDS
    with engine.connect() as conn:
        assert _links(conn) == before
        assert str(conn.execute(text("SELECT pg_typeof(id) FROM transactions LIMIT 1")).scalar()) == "integer"
        # New rows get the next number by themselves again
        conn.execute(text("INSERT INTO families DEFAULT VALUES"))
        assert conn.execute(text("SELECT count(DISTINCT id) FROM families")).scalar() == 3
    upgrade_database(url)  # and it can go forward again
    assert _version(engine) == LATEST


def test_a_database_without_rows_survives_the_uuid_revision_both_ways(url, engine):
    upgrade_database(url)
    command.downgrade(alembic_config(url), BEFORE_UUIDS)
    upgrade_database(url)

    assert _version(engine) == LATEST


# --- 0020: a transaction can be left out of the totals (TKT-87) ---------------------------------------------------------


def _ids_and_transactions_before_0020(engine):
    """Rows at revision 0019 (UUID ids): a transfer, a card payment, a balance adjustment, a purchase, and a family's own
    category called "Transferência" in another group."""
    with engine.begin() as conn:
        groups = dict(conn.execute(text("SELECT name, id FROM category_groups")).all())
        family = conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid()) RETURNING id")).scalar()
        user = conn.execute(
            text(
                "INSERT INTO users (id, family_id, google_id, name, email) "
                "VALUES (gen_random_uuid(), :f, 'g', 'Ana', 'a@e.com') RETURNING id"
            ),
            {"f": family},
        ).scalar()
        categories = {}
        for key, name, group in [
            ("transfer", "🔄 Transferência", "Transferências"),
            ("card", "💳 Pagamento de fatura do cartão", "Transferências"),
            ("adjust", "🧮 Ajustes de saldo", "Transferências"),
            ("food", "🛒 Supermercado", "Alimentação"),
            ("lookalike", "Transferência", "Outros"),  # same words, but not in the group of transfers
        ]:
            categories[key] = conn.execute(
                text("INSERT INTO categories (id, name, group_id) VALUES (gen_random_uuid(), :n, :g) RETURNING id"),
                {"n": name, "g": groups[group]},
            ).scalar()
        for key, category in categories.items():
            conn.execute(
                text(
                    "INSERT INTO transactions (id, family_id, user_id, label, value, category_id) "
                    "VALUES (gen_random_uuid(), :f, :u, :l, 100, :c)"
                ),
                {"f": family, "u": user, "l": key, "c": category},
            )
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value) "
                "VALUES (gen_random_uuid(), :f, :u, 'no category', 100)"
            ),
            {"f": family, "u": user},
        )


def test_a_database_with_the_uuid_revision_is_recognised_and_brought_to_the_latest(url, engine):
    command.upgrade(alembic_config(url), "0019")
    _forget_history(engine)

    assert detect_revision(inspect(engine)) == "0019"
    upgrade_database(url)

    assert _version(engine) == LATEST
    assert "excluded" in {c["name"] for c in inspect(engine).get_columns("transactions")}


def test_existing_transfers_and_card_payments_are_left_out_of_the_totals_and_everything_else_keeps_counting(
    url, engine
):
    command.upgrade(alembic_config(url), "0019")
    _ids_and_transactions_before_0020(engine)

    upgrade_database(url)

    with engine.connect() as conn:
        left_out = dict(conn.execute(text("SELECT label, excluded FROM transactions")).all())
    assert left_out == {
        "transfer": True,
        "card": True,
        "adjust": False,  # a correction of a balance is not a move between accounts
        "food": False,
        "lookalike": False,  # not in the group of transfers
        "no category": False,
    }


def test_undoing_the_left_out_revision_only_drops_its_column(url, engine):
    command.upgrade(alembic_config(url), "head")

    command.downgrade(alembic_config(url), "0019")

    assert _version(engine) == "0019"
    assert "excluded" not in {c["name"] for c in inspect(engine).get_columns("transactions")}
    upgrade_database(url)
    assert _version(engine) == LATEST


# --- 0021: sign-in for the Claude connector (TKT-72) ---------------------------------------------------------------------


def test_undoing_the_connector_revision_drops_only_its_tables_and_it_can_go_forward_again(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid())"))

    command.downgrade(alembic_config(url), BEFORE_CONNECTOR)

    names = set(inspect(engine).get_table_names())
    assert names.isdisjoint({"oauth_clients", "oauth_codes", "oauth_grants"})
    assert {"families", "users", "transactions"} <= names
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM families")).scalar() == 1
    upgrade_database(url)
    assert _version(engine) == LATEST


# --- 0022: an index on a family's transactions by date (TKT-91) -------------------------------------------------------------


def _index_names(engine):
    return {i["name"] for i in inspect(engine).get_indexes("transactions")}


def test_the_transactions_index_is_made_and_undone_without_touching_the_rows(url, engine):
    command.upgrade(alembic_config(url), BEFORE_INDEX)
    assert "ix_transactions_family_date" not in _index_names(engine)
    with engine.begin() as conn:
        family = conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid()) RETURNING id")).scalar()
        user = conn.execute(
            text(
                "INSERT INTO users (id, family_id, google_id, name, email) "
                "VALUES (gen_random_uuid(), :f, 'g', 'Ana', 'a@e.com') RETURNING id"
            ),
            {"f": family},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO transactions (id, family_id, user_id, label, value) "
                "VALUES (gen_random_uuid(), :f, :u, 'Almoço', 100)"
            ),
            {"f": family, "u": user},
        )

    upgrade_database(url)
    assert "ix_transactions_family_date" in _index_names(engine)
    command.downgrade(alembic_config(url), BEFORE_INDEX)

    assert "ix_transactions_family_date" not in _index_names(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM transactions")).scalar() == 1
    upgrade_database(url)
    assert _version(engine) == LATEST


def test_a_database_without_the_index_is_recognised_as_before_it(url, engine):
    command.upgrade(alembic_config(url), BEFORE_INDEX)
    _forget_history(engine)

    assert detect_revision(inspect(engine)) == BEFORE_INDEX


# --- 0023: the groups in order of priority ---------------------------------------------------------------------------------


def test_the_groups_are_put_in_order_of_priority_and_a_group_of_its_own_goes_last(url, engine):
    from api.utils.budget_order import GROUP_ORDER

    command.upgrade(alembic_config(url), "0022")
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO category_groups (id, name, position) VALUES (gen_random_uuid(), 'Meu grupo', 99)")
        )

    upgrade_database(url)

    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM category_groups ORDER BY position")).scalars().all()
    assert names == [*GROUP_ORDER, "Meu grupo"]  # the migration's own copy of the order must match the page's
    assert names.index("Moradia") < names.index("Alimentação") < names.index("Compras")


# --- 0024: a budget of 0 is a plan, "no plan" is a missing amount ---------------------------------------------------------


def test_old_zero_budgets_become_empty_rows_so_they_keep_meaning_stop(url, engine):
    command.upgrade(alembic_config(url), "0023")
    with engine.begin() as conn:
        family = conn.execute(text("INSERT INTO families (id) VALUES (gen_random_uuid()) RETURNING id")).scalar()
        group = conn.execute(text("SELECT id FROM category_groups LIMIT 1")).scalar()
        category = conn.execute(
            text("INSERT INTO categories (id, name, group_id) VALUES (gen_random_uuid(), 'X', :g) RETURNING id"),
            {"g": group},
        ).scalar()
        for month, amount in (("2026-10-01", 500), ("2026-11-01", 0)):
            conn.execute(
                text(
                    "INSERT INTO budgets (id, family_id, category_id, month, amount) VALUES (gen_random_uuid(), :f, :c, :m, :a)"
                ),
                {"f": family, "c": category, "m": month, "a": amount},
            )

    upgrade_database(url)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT amount FROM budgets ORDER BY month")).scalars().all() == [500, None]
    command.downgrade(alembic_config(url), "0023")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT amount FROM budgets ORDER BY month")).scalars().all() == [500, 0]

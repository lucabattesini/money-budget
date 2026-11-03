"""Seeding the default categories is a command, not a side effect of importing a module."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from db.upgrade import upgrade_database

BACK_END = Path(__file__).resolve().parents[2]


def _run(url, *args):
    env = {**os.environ, "DB_URL": url}
    return subprocess.run([sys.executable, *args], cwd=BACK_END, env=env, capture_output=True, text=True)


def test_importing_the_seed_module_does_nothing(url):
    result = _run(url, "-c", "import db.seed")

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_the_seed_command_adds_the_default_categories_once(url, engine):
    upgrade_database(url)

    assert _run(url, "-m", "db.seed").returncode == 0
    with engine.connect() as conn:
        first = conn.execute(text("SELECT count(*) FROM categories")).scalar()
    assert _run(url, "-m", "db.seed").returncode == 0
    with engine.connect() as conn:
        second = conn.execute(text("SELECT count(*) FROM categories")).scalar()

    assert first > 10
    assert second == first


def test_the_seed_command_fails_loudly_when_it_cannot_seed(url):
    # No tables yet (the upgrade was not run): the command must not pretend everything is fine
    result = _run(url, "-m", "db.seed")

    assert result.returncode != 0
    assert "categories" in result.stderr


def _seeded(url, engine):
    upgrade_database(url)
    assert _run(url, "-m", "db.seed").returncode == 0


def test_the_seed_gives_every_default_category_the_group_of_the_agreed_list(url, engine):
    from db.seed import DEFAULT_GROUPS, display_name

    _seeded(url, engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT g.name, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).all()
    assert sorted(rows) == sorted(
        (group, display_name(name)) for group, names in DEFAULT_GROUPS.items() for name in names
    )
    assert len(rows) == 39  # 26 expense categories plus the ones for income, transfers and investments


def test_seeding_twice_adds_no_group_and_no_category(url, engine):
    _seeded(url, engine)
    with engine.connect() as conn:
        before = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("category_groups", "categories")]

    assert _run(url, "-m", "db.seed").returncode == 0

    with engine.connect() as conn:
        after = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("category_groups", "categories")]
    assert after == before == [12, 39]


def test_the_seed_repairs_a_missing_default_category_without_touching_the_others(url, engine):
    _seeded(url, engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM categories WHERE name LIKE '% Viagem'"))

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        group = conn.execute(
            text(
                "SELECT g.name FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE c.name LIKE '% Viagem'"
            )
        ).scalar()
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 39
    assert group == "Lazer"


def test_a_family_with_a_category_of_the_same_name_does_not_stop_the_default_from_being_created(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO families (id) VALUES (1)"))
        conn.execute(
            text("INSERT INTO categories (family_id, name, group_id) SELECT 1, 'Pets', id FROM category_groups LIMIT 1")
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM categories WHERE name LIKE '% Pets' AND family_id IS NULL")
            ).scalar()
            == 1
        )


def test_there_are_default_categories_for_income_transfers_and_investments(url, engine):
    _seeded(url, engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT g.name, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).all()
    from api.utils.category_names import plain_name

    by_group = {}
    for group, name in rows:
        by_group.setdefault(group, set()).add(plain_name(name))
    assert {"Salário", "Renda extra e freelance", "Reembolsos"} <= by_group["Receitas"]
    assert {"Transferência entre contas", "Pagamento de fatura do cartão"} <= by_group["Transferências"]
    assert {"Investimentos", "Fundo de Emergência", "Renda fixa", "Ações e fundos"} <= by_group["Investimentos"]
    assert "Investimentos" not in by_group["Finanças"] and "Fundo de Emergência" not in by_group["Finanças"]


def test_a_database_made_by_the_migration_alone_gets_the_new_categories_from_the_seed_without_touching_old_ones(
    url, engine
):
    upgrade_database(url)
    with engine.begin() as conn:  # what an existing database has: the old default categories, already grouped
        conn.execute(
            text(
                "INSERT INTO categories (name, group_id) "
                "SELECT 'Investimentos', id FROM category_groups WHERE name = 'Investimentos'"
            )
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM categories WHERE name LIKE '%Investimentos' AND name NOT LIKE '%de investimentos'"
                )
            ).scalar()
            == 1
        )
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name LIKE '% Salário'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 39


def test_a_default_category_that_differs_only_in_case_is_not_added_twice(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:  # what the migration leaves when it groups an old "aluguel" by name
        conn.execute(
            text(
                "INSERT INTO categories (name, group_id) SELECT 'aluguel', id FROM category_groups WHERE name = 'Casa'"
            )
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories WHERE lower(name) = 'aluguel'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 39


def test_two_seeds_running_at_the_same_time_both_succeed_and_add_nothing_twice(url, engine):
    """Two API containers starting together: neither may fail on the unique group name or duplicate a category."""
    upgrade_database(url)
    env = {**os.environ, "DB_URL": url}
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "db.seed"],
            cwd=BACK_END,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    results = [(p.wait(timeout=120), p.stderr.read()) for p in processes]

    assert [code for code, _ in results] == [0, 0, 0, 0], results
    with engine.connect() as conn:
        counts = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("category_groups", "categories")]
    assert counts == [12, 39]


def test_the_migrations_frozen_grouping_still_agrees_with_the_seed_for_what_it_covers():
    """The migration keeps its own copy of the grouping. Adding default categories to the seed is fine, but moving
    one to another group, or renaming or reordering a group, would leave existing databases different from new ones:
    that needs a new migration, and this test says so."""
    import importlib.util

    from db.seed import DEFAULT_GROUPS

    path = BACK_END / "migrations" / "versions" / "0010_category_groups.py"
    spec = importlib.util.spec_from_file_location("migration_0010", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert list(migration.GROUPS) == list(DEFAULT_GROUPS)  # the same groups, in the same order
    for group, names in migration.GROUPS.items():
        missing = set(names) - set(DEFAULT_GROUPS[group])
        assert not missing, f"{group}: the seed no longer groups {missing}"


def test_every_default_category_has_an_emoji_in_front_of_its_name(url, engine):
    from api.utils.category_names import plain_name
    from db.seed import default_categories

    _seeded(url, engine)

    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM categories WHERE family_id IS NULL")).scalars().all()
    assert sorted(plain_name(name) for name in names) == sorted(default_categories)
    assert all(name != plain_name(name) and name.endswith(" " + plain_name(name)) for name in names), names


def test_every_default_category_has_an_emoji_chosen_for_it():
    """Whoever adds a default category to DEFAULT_GROUPS must also pick its emoji in DEFAULT_EMOJIS."""
    from db.seed import DEFAULT_EMOJIS, default_categories

    assert set(DEFAULT_EMOJIS) == set(default_categories)
    assert all(emoji.strip() == emoji and emoji for emoji in DEFAULT_EMOJIS.values())


def test_a_default_stored_without_its_emoji_is_not_added_a_second_time(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:  # a database from before the emojis
        conn.execute(
            text(
                "INSERT INTO categories (name, group_id) SELECT 'Aluguel', id FROM category_groups WHERE name = 'Casa'"
            )
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name LIKE '%Aluguel'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 39


def test_the_migrations_frozen_emojis_still_agree_with_the_seed_for_what_it_covers():
    """Migration 0011 keeps its own copy of the emojis. A default whose emoji changes in the seed would then differ
    between old and new databases: that needs a new migration, and this test says so."""
    import importlib.util

    from db.seed import DEFAULT_EMOJIS

    path = BACK_END / "migrations" / "versions" / "0011_category_emojis.py"
    spec = importlib.util.spec_from_file_location("migration_0011", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.EMOJIS.items() <= DEFAULT_EMOJIS.items()

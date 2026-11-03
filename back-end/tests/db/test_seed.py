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
    assert len(rows) == 51  # the default categories of Monarch Money, in Portuguese


def test_seeding_twice_adds_no_group_and_no_category(url, engine):
    _seeded(url, engine)
    with engine.connect() as conn:
        before = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("category_groups", "categories")]

    assert _run(url, "-m", "db.seed").returncode == 0

    with engine.connect() as conn:
        after = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("category_groups", "categories")]
    assert after == before == [14, 51]


def test_the_seed_repairs_a_missing_default_category_without_touching_the_others(url, engine):
    _seeded(url, engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM categories WHERE name LIKE '% Viagem e Férias'"))

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        group = conn.execute(
            text(
                "SELECT g.name FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE c.name LIKE '% Viagem e Férias'"
            )
        ).scalar()
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 51
    assert group == "Viagem e Estilo de Vida"


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


def test_there_are_default_categories_for_income_and_for_transfers(url, engine):
    _seeded(url, engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT g.name, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).all()
    from api.utils.category_names import plain_name

    by_group = {}
    for group, name in rows:
        by_group.setdefault(group, set()).add(plain_name(name))
    assert {"Salário", "Juros", "Renda de negócios", "Outras receitas"} <= by_group["Receitas"]
    assert {"Transferência", "Pagamento de fatura do cartão", "Ajustes de saldo"} <= by_group["Transferências"]
    assert "Sem categoria" in by_group["Outros"]  # where the assistant puts what it cannot place


def test_a_database_made_by_the_migration_alone_gets_the_missing_categories_from_the_seed_without_touching_old_ones(
    url, engine
):
    upgrade_database(url)
    with engine.begin() as conn:  # what the migration leaves for an existing database: some defaults, already grouped
        conn.execute(
            text("INSERT INTO categories (name, group_id) SELECT '💰 Salário', id FROM category_groups WHERE name = 'Receitas'")
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name LIKE '%Salário'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name LIKE '% Juros'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 51


def test_a_default_category_that_differs_only_in_case_is_not_added_twice(url, engine):
    upgrade_database(url)
    with engine.begin() as conn:  # what the migration leaves when it groups an old "aluguel" by name
        conn.execute(
            text(
                "INSERT INTO categories (name, group_id) SELECT 'aluguel', id FROM category_groups WHERE name = 'Moradia'"
            )
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories WHERE lower(name) = 'aluguel'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 51


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
    assert counts == [14, 51]


def test_the_migrations_frozen_lists_agree_with_the_seed():
    """Migration 0012 keeps its own copy of the groups and emojis. Changing the seed's list (moving or renaming a
    default category, a group or an emoji) would leave existing databases different from new ones: that needs a new
    migration, and this test says so."""
    import importlib.util

    from db.seed import DEFAULT_EMOJIS, DEFAULT_GROUPS

    path = BACK_END / "migrations" / "versions" / "0012_monarch_categories.py"
    spec = importlib.util.spec_from_file_location("migration_0012", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.GROUPS == DEFAULT_GROUPS
    assert list(migration.GROUPS) == list(DEFAULT_GROUPS)  # in the same order
    assert migration.EMOJIS == DEFAULT_EMOJIS


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
                "INSERT INTO categories (name, group_id) SELECT 'Aluguel', id FROM category_groups WHERE name = 'Moradia'"
            )
        )

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name LIKE '%Aluguel'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 51


def test_the_development_seed_works_with_default_categories_that_start_with_an_emoji(url, engine):
    """db.seed_dev looks the defaults up by their words ("Aluguel"), but they are stored as "🏠 Aluguel"."""
    upgrade_database(url)
    _run(url, "-m", "db.seed")

    result = _run(url, "-m", "db.seed_dev")

    assert result.returncode == 0, result.stderr
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM transactions")).scalar() > 50
        assert conn.execute(text("SELECT count(*) FROM transactions WHERE category_id IS NULL")).scalar() == 0


def test_the_assistants_category_list_is_the_default_categories_without_income_and_transfers():
    """The assistant registers expenses, so it may pick any default category except those two groups."""
    from typing import get_args

    from db.seed import DEFAULT_GROUPS
    from schemas.agents_schemas import CategoryType

    expected = [n for group, names in DEFAULT_GROUPS.items() if group not in ("Receitas", "Transferências") for n in names]
    assert list(get_args(CategoryType)) == expected

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
    from db.seed import DEFAULT_GROUPS

    _seeded(url, engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT g.name, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).all()
    assert sorted(rows) == sorted((group, name) for group, names in DEFAULT_GROUPS.items() for name in names)
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
        conn.execute(text("DELETE FROM categories WHERE name = 'Viagem'"))

    _run(url, "-m", "db.seed")

    with engine.connect() as conn:
        group = conn.execute(
            text("SELECT g.name FROM categories c JOIN category_groups g ON g.id = c.group_id WHERE c.name = 'Viagem'")
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
            conn.execute(text("SELECT count(*) FROM categories WHERE name = 'Pets' AND family_id IS NULL")).scalar()
            == 1
        )


def test_there_are_default_categories_for_income_transfers_and_investments(url, engine):
    _seeded(url, engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT g.name, c.name FROM categories c JOIN category_groups g ON g.id = c.group_id")
        ).all()
    by_group = {}
    for group, name in rows:
        by_group.setdefault(group, set()).add(name)
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
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name = 'Investimentos'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories WHERE name = 'Salário'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM categories")).scalar() == 39

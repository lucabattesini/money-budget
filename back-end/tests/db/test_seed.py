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

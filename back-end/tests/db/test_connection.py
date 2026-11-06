"""There is no hidden database: without DB_URL the app says what to set instead of creating a SQLite file."""

import os
import subprocess
import sys
from pathlib import Path

BACK_END = Path(__file__).resolve().parents[2]


def test_a_missing_db_url_is_a_clear_error_not_a_silent_sqlite_file(tmp_path):
    env = {**os.environ, "DB_URL": ""}  # empty counts as missing, and .env cannot override it
    before = set(BACK_END.glob("*.db"))

    result = subprocess.run(
        [sys.executable, "-c", "import db.connection"], cwd=BACK_END, env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "DB_URL is not set" in result.stderr
    assert "PostgreSQL" in result.stderr
    assert set(BACK_END.glob("*.db")) == before  # nothing was created


def _engine_facts(**env_changes):
    """Import db.connection in a fresh process with these settings and say what the engine ended up with."""
    env = {**os.environ, **env_changes}
    code = (
        "import db.connection as c;"
        "print(c.engine.url.render_as_string(hide_password=False));"
        "print(c.engine.pool.size(), c.engine.pool._max_overflow, c.engine.pool._pre_ping)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=BACK_END, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    url, pool = result.stdout.strip().splitlines()
    return url, pool


def test_the_pool_is_small_when_asked_and_checks_connections_before_using_them():
    _url, pool = _engine_facts(DB_POOL_SIZE="2", DB_MAX_OVERFLOW="0")

    assert pool == "2 0 True"


def test_the_password_can_come_apart_from_the_url_and_is_quoted_safely():
    url, _pool = _engine_facts(
        DB_URL="postgresql+psycopg2://app@/money_budget?host=/cloudsql/p:r:i", DB_PASSWORD="p@ss/w:rd%1"
    )

    # The password is quoted; the socket path is written in its encoded form, which means the same thing
    assert url == "postgresql+psycopg2://app:p%40ss%2Fw%3Ard%251@/money_budget?host=%2Fcloudsql%2Fp%3Ar%3Ai"


def test_without_a_separate_password_the_url_is_used_as_it_is():
    url, _pool = _engine_facts(DB_URL="postgresql+psycopg2://a:b@h:5432/d", DB_PASSWORD="")

    assert url == "postgresql+psycopg2://a:b@h:5432/d"

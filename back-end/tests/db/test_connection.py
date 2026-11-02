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

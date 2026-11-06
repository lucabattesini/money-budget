"""In production the API also serves the built web app, on the same address (so there is no CORS to set up)."""

import importlib

import pytest
from fastapi.testclient import TestClient

import api.app


@pytest.fixture
def served(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>the web app</html>")
    (tmp_path / "assets" / "main.js").write_text("console.log('hi')")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    import config

    importlib.reload(config)
    importlib.reload(api.app)
    yield TestClient(api.app.app)
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(api.app)


def test_the_front_page_and_its_files_are_served(served):
    page = served.get("/")
    script = served.get("/assets/main.js")

    assert (page.status_code, "the web app" in page.text) == (200, True)
    assert (script.status_code, script.text) == (200, "console.log('hi')")


def test_the_api_addresses_still_win_over_the_web_files(served):
    assert served.get("/categories/").status_code in (401, 403)  # the API's own answer: login required
    assert served.get("/docs").status_code == 200
    assert served.get("/webhook/").status_code == 400  # the webhook check, not a missing file


def test_a_file_that_does_not_exist_is_not_found(served):
    assert served.get("/nothing-here.js").status_code == 404


def test_without_a_web_app_folder_nothing_is_served_at_the_root(client):
    assert client.get("/").status_code == 404

"""Settings from the environment (`config.py`) and where the app uses them."""

import importlib

import pytest
from fastapi.testclient import TestClient

import config
from api.app import app


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
def test_env_flag_accepts_truthy_values(monkeypatch, value):
    monkeypatch.setenv("SOME_FLAG", value)

    assert config.env_flag("SOME_FLAG") is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "banana"])
def test_env_flag_treats_everything_else_as_off(monkeypatch, value):
    monkeypatch.setenv("SOME_FLAG", value)

    assert config.env_flag("SOME_FLAG", default=True) is False


def test_env_flag_uses_the_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)

    assert config.env_flag("SOME_FLAG") is False
    assert config.env_flag("SOME_FLAG", default=True) is True


def test_sql_logging_is_off_unless_asked_for(monkeypatch):
    monkeypatch.delenv("SQL_ECHO", raising=False)
    try:
        assert importlib.reload(config).SQL_ECHO is False

        monkeypatch.setenv("SQL_ECHO", "true")
        assert importlib.reload(config).SQL_ECHO is True
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_model_name_and_front_url_can_be_set_and_have_defaults(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "some-other-model")
    monkeypatch.setenv("FRONT_URL", "https://app.example.com/")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.GEMINI_MODEL == "some-other-model"
        assert reloaded.FRONT_URL == "https://app.example.com"  # trailing slash removed

        monkeypatch.delenv("GEMINI_MODEL")
        monkeypatch.delenv("FRONT_URL")
        reloaded = importlib.reload(config)
        assert reloaded.GEMINI_MODEL == "gemini-3.5-flash"
        assert reloaded.FRONT_URL == "http://localhost:5173"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_the_database_engine_does_not_log_sql_by_default():
    from db.connection import engine

    assert engine.echo is False


def test_every_agent_uses_the_configured_model():
    from agents.orchestrator import run as orchestrator
    from agents.query import run as query
    from agents.recorder import run as recorder
    from agents.secretary import run as secretary

    for module in (orchestrator, query, recorder, secretary):
        assert module.GEMINI_MODEL == config.GEMINI_MODEL


def _preflight(origin):
    return TestClient(app).options(
        "/transactions/",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


def test_cors_allows_the_configured_web_app_address():
    response = _preflight(config.FRONT_URL)

    assert response.headers.get("access-control-allow-origin") == config.FRONT_URL


def test_cors_rejects_other_websites():
    response = _preflight("https://evil.example.com")

    assert "access-control-allow-origin" not in response.headers

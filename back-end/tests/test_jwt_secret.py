import pytest

from api.controllers.auth_controller import DEV_JWT_SECRET, load_jwt_secret


def test_uses_configured_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "abc123")
    assert load_jwt_secret() == "abc123"


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_secret_is_rejected(monkeypatch, value):
    monkeypatch.setenv("JWT_SECRET", value)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        load_jwt_secret()


def test_missing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(RuntimeError):
        load_jwt_secret()


def test_production_mode_still_requires_a_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        load_jwt_secret()


def test_development_mode_allows_the_dev_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("APP_ENV", "development")
    assert load_jwt_secret() == DEV_JWT_SECRET

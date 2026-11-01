import pytest

from api.controllers.auth_controller import DEV_JWT_SECRET, load_jwt_secret


def test_uses_configured_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "abc123")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert load_jwt_secret() == "abc123"


def test_configured_secret_wins_over_development_mode(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "abc123")
    monkeypatch.setenv("APP_ENV", "development")
    assert load_jwt_secret() == "abc123"


@pytest.mark.parametrize("secret", ["", "   ", None])
@pytest.mark.parametrize("app_env", [None, "", "production"])
def test_missing_or_blank_secret_is_rejected(monkeypatch, secret, app_env):
    for name, value in (("JWT_SECRET", secret), ("APP_ENV", app_env)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        load_jwt_secret()


@pytest.mark.parametrize("app_env", ["development", "Development", "  DEVELOPMENT "])
def test_development_mode_allows_the_dev_secret(monkeypatch, app_env):
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("APP_ENV", app_env)
    assert load_jwt_secret() == DEV_JWT_SECRET

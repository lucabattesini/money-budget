import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest

from api.controllers import auth_controller
from schemas.tables import Users

PROTECTED = ("post", "/transactions/")


def _call(client, headers=None):
    method, path = PROTECTED
    return getattr(client, method)(path, json={}, headers=headers or {})


def _token(payload, secret=None, algorithm="HS256"):
    return jwt.encode(payload, secret or auth_controller.JWT_SECRET, algorithm=algorithm)


def _future():
    return datetime.now(timezone.utc) + timedelta(hours=1)


# --- bearer tokens ---------------------------------------------------------


def test_missing_token_is_unauthorized(client):
    assert _call(client).status_code == 401


def test_malformed_token_is_unauthorized(client):
    response = _call(client, {"Authorization": "Bearer nonsense"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_token_signed_with_another_secret_is_unauthorized(client, user):
    forged = _token({"user_id": str(user.id), "exp": _future()}, secret="a-different-secret-0123456789abcdef")

    response = _call(client, {"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_unsigned_token_is_unauthorized(client, user):
    unsigned = jwt.encode({"user_id": str(user.id), "exp": _future()}, key=None, algorithm="none")

    response = _call(client, {"Authorization": f"Bearer {unsigned}"})

    assert response.status_code == 401


def test_token_without_user_id_is_unauthorized(client):
    response = _call(client, {"Authorization": f"Bearer {_token({'exp': _future()})}"})

    assert response.status_code == 401


def test_expired_token_is_unauthorized(client, user):
    expired = _token({"user_id": str(user.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)})

    response = _call(client, {"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_token_round_trips_the_user_id():
    user_id = uuid.uuid4()

    assert UUID(auth_controller.decode_jwt(auth_controller.create_jwt(user_id))["user_id"]) == user_id


def test_a_token_made_before_ids_were_uuids_asks_for_a_new_login(client):
    """Tokens from the counting-number days hold a number: they are refused, so the person logs in again (TKT-74)."""
    old = _token({"user_id": 7, "exp": _future()})

    response = _call(client, {"Authorization": f"Bearer {old}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_a_token_without_a_user_is_unauthorized(client):
    response = _call(client, {"Authorization": f"Bearer {_token({'exp': _future()})}"})

    assert response.status_code == 401


# --- Google login ------------------------------------------------------------


@pytest.fixture
def google(monkeypatch):
    """Fake only Google's network call, so our own verify_google_token wrapper still runs."""
    calls = []
    payload = {"sub": "g-123", "name": "New Person", "email": "new@example.com", "picture": "http://pic"}

    def fake_verify(token, request, audience, **kwargs):
        calls.append({"token": token, "audience": audience, **kwargs})
        if isinstance(payload, Exception):
            raise payload
        return dict(payload)

    monkeypatch.setattr(auth_controller.id_token, "verify_oauth2_token", fake_verify)
    return calls, payload


def test_google_login_creates_the_user_and_returns_a_working_token(client, db, google):
    calls, _ = google

    response = client.post("/auth/google", json={"id_token": "the-google-token"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["picture"] == "http://pic"
    row = db.query(Users).filter_by(google_id="g-123").one()
    assert str(row.id) == data["user"]["id"]
    assert auth_controller.decode_jwt(data["token"])["user_id"] == str(row.id)
    # the token we got back really authenticates the user
    assert client.get("/user/me", headers={"Authorization": f"Bearer {data['token']}"}).status_code == 200
    # Google is asked to verify the token we received, for our own client id
    assert calls[0]["token"] == "the-google-token"
    assert calls[0]["audience"] == "test-google-client-id"


def test_logging_in_twice_does_not_duplicate_the_user(client, db, google):
    _, payload = google

    first = client.post("/auth/google", json={"id_token": "t"}).json()["data"]["user"]
    payload["name"] = "Renamed Person"
    second = client.post("/auth/google", json={"id_token": "t"}).json()["data"]["user"]

    assert second["id"] == first["id"]
    assert second["name"] == "Renamed Person"
    assert db.query(Users).filter_by(google_id="g-123").count() == 1


def test_google_login_can_attach_a_whatsapp_number(client, google):
    response = client.post("/auth/google", json={"id_token": "t", "whatsapp_phone": "5511999990000"})

    assert response.json()["data"]["user"]["whatsapp_phone"] == "5511999990000"


def test_google_login_with_a_number_that_belongs_to_someone_else_is_a_conflict(client, db, google, make_user):
    owner = make_user(whatsapp_phone="5511999990000")

    response = client.post("/auth/google", json={"id_token": "t", "whatsapp_phone": "5511999990000"})

    assert response.status_code == 409
    assert db.query(Users).filter_by(google_id="g-123").count() == 0  # the login did not half-happen
    assert db.get(Users, owner.id).whatsapp_phone == "5511999990000"


def test_invalid_google_token_is_unauthorized(client, google, monkeypatch):
    def invalid(*args, **kwargs):
        raise ValueError("Token expired")

    monkeypatch.setattr(auth_controller.id_token, "verify_oauth2_token", invalid)

    response = client.post("/auth/google", json={"id_token": "bad"})

    assert response.status_code == 401
    assert "Token expired" in response.json()["detail"]


def test_unexpected_login_failure_is_a_server_error(client, google, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(auth_controller, "upsert_user_ctrl", boom)

    response = client.post("/auth/google", json={"id_token": "t"})

    assert response.status_code == 500


def test_login_requires_an_id_token(client):
    assert client.post("/auth/google", json={}).status_code == 422

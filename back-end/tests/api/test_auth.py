from datetime import datetime, timedelta, timezone

import jwt

from api.controllers import auth_controller


def test_protected_route_requires_a_token(client):
    response = client.post("/transactions/", json={})

    assert response.status_code in (401, 403)


def test_rejects_an_invalid_token(client):
    response = client.post("/transactions/", json={}, headers={"Authorization": "Bearer nonsense"})

    assert response.status_code == 401


def test_rejects_an_expired_token(client, user):
    expired = jwt.encode(
        {"user_id": user.id, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        auth_controller.JWT_SECRET,
        algorithm=auth_controller.JWT_ALGORITHM,
    )

    response = client.post("/transactions/", json={}, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_me_returns_the_logged_in_user(client, user, auth_headers):
    response = client.get("/user/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == user.email


def test_google_login_creates_a_user_and_returns_a_token(client, monkeypatch):
    monkeypatch.setattr(
        auth_controller,
        "verify_google_token",
        lambda token: {"sub": "g-123", "name": "New Person", "email": "new@example.com"},
    )

    response = client.post("/auth/google", json={"id_token": "fake"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == "new@example.com"
    decoded = auth_controller.decode_jwt(data["token"])
    assert decoded["user_id"] == data["user"]["id"]


def test_google_login_with_a_bad_token_is_rejected(client, monkeypatch):
    def invalid(token):
        raise ValueError("Token expired")

    monkeypatch.setattr(auth_controller, "verify_google_token", invalid)

    response = client.post("/auth/google", json={"id_token": "bad"})

    assert response.status_code == 401


def test_update_phone(client, user, auth_headers):
    response = client.patch("/user/me/phone", json={"whatsapp_phone": "5511999999999"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["whatsapp_phone"] == "5511999999999"

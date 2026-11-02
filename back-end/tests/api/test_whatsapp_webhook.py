from types import SimpleNamespace

import pytest

from api.controllers import whatsapp_controller

VERIFY = {"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "challenge-123"}


def message_payload(sender="5511999990000", text="gastei 10 de almoço"):
    return {"entry": [{"changes": [{"value": {"messages": [{"from": sender, "text": {"body": text}}]}}]}]}


@pytest.fixture
def graph(monkeypatch):
    """Replace the chatbot graph; records what it was invoked with."""
    calls = []

    def invoke(state):
        calls.append(state)
        return {"final_response": "resposta do bot"}

    monkeypatch.setattr(whatsapp_controller, "app", SimpleNamespace(invoke=invoke))
    return calls


# --- webhook verification (GET) ------------------------------------------------


def test_verification_echoes_the_challenge(client):
    response = client.get("/webhook/", params=VERIFY)

    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_verification_with_the_wrong_token_is_forbidden(client):
    response = client.get("/webhook/", params={**VERIFY, "hub.verify_token": "wrong"})

    assert response.status_code == 403
    assert "challenge-123" not in response.text


def test_verification_with_the_wrong_mode_is_forbidden(client):
    assert client.get("/webhook/", params={**VERIFY, "hub.mode": "unsubscribe"}).status_code == 403


@pytest.mark.parametrize("missing", ["hub.mode", "hub.verify_token"])
def test_verification_without_required_parameters_is_a_bad_request(client, missing):
    params = {k: v for k, v in VERIFY.items() if k != missing}

    assert client.get("/webhook/", params=params).status_code == 400


# --- incoming messages (POST) --------------------------------------------------


def test_message_from_a_known_number_goes_through_the_chatbot_and_the_reply_is_sent(
    client, make_user, graph, sent_messages
):
    user = make_user(whatsapp_phone="5511999990000")

    response = client.post("/webhook/", json=message_payload(text="gastei 10 de almoço"))

    assert response.json() == {"status": "success", "reply": "resposta do bot"}
    assert graph == [{"user_message": "gastei 10 de almoço", "user_id": user.id}]
    assert sent_messages == [("5511999990000", "resposta do bot")]


def test_message_from_an_unknown_number_gets_a_signup_link_and_never_reaches_the_chatbot(client, graph, sent_messages):
    response = client.post("/webhook/", json=message_payload(sender="5500000000000"))

    reply = response.json()["reply"]
    assert "ainda não tem uma conta" in reply
    assert "phone=5500000000000" in reply
    assert graph == []
    assert sent_messages == [("5500000000000", reply)]


def test_message_is_routed_to_the_user_that_owns_the_number(client, make_user, graph):
    make_user(whatsapp_phone="5511111111111")
    owner = make_user(whatsapp_phone="5522222222222")

    client.post("/webhook/", json=message_payload(sender="5522222222222"))

    assert graph[0]["user_id"] == owner.id


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"entry": []},
        {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]},  # delivery receipt, no messages
        {"entry": [{"changes": [{"value": {"messages": [{"from": "5511", "image": {"id": "1"}}]}}]}]},  # not text
    ],
)
def test_payloads_without_a_text_message_are_acknowledged_and_ignored(client, graph, sent_messages, body):
    response = client.post("/webhook/", json=body)

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert graph == []
    assert sent_messages == []


def test_a_chatbot_failure_is_reported_in_the_body_but_the_webhook_still_answers_200(
    client, make_user, monkeypatch, sent_messages
):
    make_user(whatsapp_phone="5511999990000")

    def broken(state):
        raise RuntimeError("gemini is down")

    monkeypatch.setattr(whatsapp_controller, "app", SimpleNamespace(invoke=broken))

    response = client.post("/webhook/", json=message_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "error", "message": "gemini is down"}
    assert sent_messages == []


# --- security and failure handling (TKT-27) -----------------------------------


def _signed(body: bytes, secret: str = "test-app-secret") -> str:
    import hashlib
    import hmac

    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.skip(reason="TKT-27: the webhook does not verify Meta's signature, so anyone can post as any user")
def test_unsigned_requests_are_rejected(client, make_user, graph, sent_messages):
    make_user(whatsapp_phone="5511999990000")

    response = client.post("/webhook/", json=message_payload())

    assert response.status_code == 403
    assert graph == []
    assert sent_messages == []


@pytest.mark.skip(reason="TKT-27: the webhook does not verify Meta's signature")
def test_requests_signed_with_the_wrong_secret_are_rejected(client, make_user, graph, monkeypatch):
    import json

    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    make_user(whatsapp_phone="5511999990000")
    body = json.dumps(message_payload()).encode()

    response = client.post(
        "/webhook/",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _signed(body, "not-the-secret")},
    )

    assert response.status_code == 403
    assert graph == []


@pytest.mark.skip(reason="TKT-27: needs the WHATSAPP_APP_SECRET signature check to exist")
def test_correctly_signed_requests_are_accepted(client, make_user, graph, monkeypatch):
    import json

    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    make_user(whatsapp_phone="5511999990000")
    body = json.dumps(message_payload()).encode()

    response = client.post(
        "/webhook/",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _signed(body)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.skip(reason="TKT-27: when the chatbot fails the user is sent nothing")
def test_the_user_is_told_when_the_chatbot_fails(client, make_user, monkeypatch, sent_messages):
    make_user(whatsapp_phone="5511999990000")

    def broken(state):
        raise RuntimeError("gemini is down")

    monkeypatch.setattr(whatsapp_controller, "app", SimpleNamespace(invoke=broken))

    client.post("/webhook/", json=message_payload())

    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "5511999990000"
    assert "gemini is down" not in sent_messages[0][1]  # a friendly message, not the raw error

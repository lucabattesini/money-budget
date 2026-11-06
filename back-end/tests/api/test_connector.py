"""The Claude connector (TKT-72): the sign-in of AI apps (OAuth with PKCE) and the tools at /mcp.

The app side is played by the tests: they register, send the person through the decision, swap the code for tokens and
call /mcp with them, exactly as the Claude app would.
"""

import base64
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from schemas.tables import Categories, Families, OAuthCode, OAuthGrant, TransactionDB


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


def _register(client, redirect=REDIRECT, name="Claude"):
    return client.post("/oauth/register", json={"client_name": name, "redirect_uris": [redirect]})


def _decision(client_id, allow=True, redirect=REDIRECT, challenge=CHALLENGE, state="xyz"):
    return {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "allow": allow,
    }


def _code_for(client, headers, client_id, **kwargs):
    answer = client.post("/oauth/authorize", json=_decision(client_id, **kwargs), headers=headers)
    assert answer.status_code == 200, answer.text
    return parse_qs(urlsplit(answer.json()["data"]["redirect_to"]).query)


def _token_form(client_id, code, verifier=VERIFIER, redirect=REDIRECT):
    return {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect,
    }


@pytest.fixture
def connect(client, headers_for):
    """Connect an app as `person`; returns the token answer (access_token, refresh_token...) and the client id."""

    def _connect(person):
        client_id = _register(client).json()["client_id"]
        code = _code_for(client, headers_for(person), client_id)["code"][0]
        tokens = client.post("/oauth/token", data=_token_form(client_id, code)).json()
        return tokens, client_id

    return _connect


def _call(client, token, method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return client.post("/mcp", json=message, headers={"Authorization": f"Bearer {token}"})


def _tool(client, token, name, arguments=None):
    answer = _call(client, token, "tools/call", {"name": name, "arguments": arguments or {}})
    assert answer.status_code == 200, answer.text
    return json.loads(answer.json()["result"]["content"][0]["text"])


def _row(**fields):
    return {
        "date": "2026-03-10",
        "description": "Almoço",
        "amount_cents": 4500,
        "type": "debit",
        "category": "Restaurantes e Bares",
        **fields,
    }


# --- discovery and registration ---------------------------------------------------------------------------------


def test_the_app_finds_where_to_sign_in(client):
    resource = client.get("/.well-known/oauth-protected-resource").json()
    server = client.get("/.well-known/oauth-authorization-server").json()
    assert resource["resource"].endswith("/mcp")
    assert resource["authorization_servers"] == [server["issuer"]]
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["token_endpoint"] == f"{server['issuer']}/oauth/token"


def test_the_public_address_setting_decides_the_addresses_in_the_discovery_pages(client, monkeypatch):
    from api.routers import oauth_router

    monkeypatch.setattr(oauth_router, "PUBLIC_URL", "https://budget.example.com")
    server = client.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"] == "https://budget.example.com"
    assert server["authorization_endpoint"] == "https://budget.example.com/oauth/authorize"
    assert client.get("/.well-known/oauth-protected-resource").json()["resource"] == "https://budget.example.com/mcp"


@pytest.mark.parametrize("redirect", ["http://evil.example/cb", "javascript:alert(1)", "https://x.example/cb#frag", ""])
def test_registration_refuses_unsafe_return_addresses(client, redirect):
    answer = _register(client, redirect)
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_redirect_uri"


def test_registration_allows_localhost_over_http(client):
    assert _register(client, "http://localhost:6274/callback").status_code == 201
    assert _register(client, "http://[::1]:6274/callback").status_code == 201


# --- the person says yes or no ----------------------------------------------------------------------------------


def test_authorize_hands_the_person_to_the_web_app_page(client):
    client_id = _register(client).json()["client_id"]
    answer = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert answer.status_code == 302
    target = answer.headers["location"]
    assert "/#/connect?" in target
    assert parse_qs(urlsplit(target).fragment.split("?", 1)[1])["app"] == ["Claude"]


def test_authorize_never_redirects_to_an_unregistered_address(client):
    client_id = _register(client).json()["client_id"]
    answer = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "https://evil.example/steal",
            "response_type": "code",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert answer.status_code == 400
    assert "location" not in answer.headers


def test_authorize_requires_pkce(client):
    client_id = _register(client).json()["client_id"]
    answer = client.get(
        "/oauth/authorize",
        params={"client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code"},
        follow_redirects=False,
    )
    assert answer.status_code == 400


def test_the_decision_needs_the_web_app_login(client):
    client_id = _register(client).json()["client_id"]
    assert client.post("/oauth/authorize", json=_decision(client_id)).status_code in (401, 403)


def test_saying_no_sends_the_app_back_with_an_error_and_no_code(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    query = _code_for(client, auth_headers, client_id, allow=False)
    assert query["error"] == ["access_denied"] and query["state"] == ["xyz"]
    assert "code" not in query


def test_the_decision_cannot_name_an_address_the_app_did_not_register(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    answer = client.post(
        "/oauth/authorize", json=_decision(client_id, redirect="https://evil.example/steal"), headers=auth_headers
    )
    assert answer.status_code == 400


# --- tokens ------------------------------------------------------------------------------------------------------


def test_a_code_is_swapped_for_tokens_once(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    code = _code_for(client, auth_headers, client_id)["code"][0]
    first = client.post("/oauth/token", data=_token_form(client_id, code))
    assert first.status_code == 200
    assert {"access_token", "refresh_token", "expires_in"} <= first.json().keys()
    assert first.json()["token_type"] == "Bearer"
    second = client.post("/oauth/token", data=_token_form(client_id, code))
    assert second.status_code == 400 and second.json()["error"] == "invalid_grant"


def test_a_wrong_pkce_verifier_is_refused_and_spends_the_code(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    code = _code_for(client, auth_headers, client_id)["code"][0]
    assert client.post("/oauth/token", data=_token_form(client_id, code, verifier="w" * 64)).status_code == 400
    assert client.post("/oauth/token", data=_token_form(client_id, code)).status_code == 400


def test_a_code_does_not_work_for_another_app_or_address(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    other_id = _register(client).json()["client_id"]
    code = _code_for(client, auth_headers, client_id)["code"][0]
    assert client.post("/oauth/token", data=_token_form(other_id, code)).status_code == 400
    code = _code_for(client, auth_headers, client_id)["code"][0]
    assert client.post("/oauth/token", data=_token_form(client_id, code, redirect=REDIRECT + "/x")).status_code == 400


def test_an_expired_code_is_refused(client, auth_headers, db):
    client_id = _register(client).json()["client_id"]
    code = _code_for(client, auth_headers, client_id)["code"][0]
    db.query(OAuthCode).update({"expires_at": _utc_now() - timedelta(seconds=1)})
    db.commit()
    assert client.post("/oauth/token", data=_token_form(client_id, code)).status_code == 400


def test_refreshing_replaces_both_tokens(client, connect, user):
    tokens, client_id = connect(user)
    answer = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "client_id": client_id, "refresh_token": tokens["refresh_token"]},
    )
    assert answer.status_code == 200
    renewed = answer.json()
    assert _call(client, renewed["access_token"], "ping").status_code == 200
    assert _call(client, tokens["access_token"], "ping").status_code == 401  # the old one stopped working
    again = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "client_id": client_id, "refresh_token": tokens["refresh_token"]},
    )
    assert again.status_code == 400


def test_an_expired_access_token_is_refused(client, connect, user, db):
    tokens, _ = connect(user)
    db.query(OAuthGrant).update({"access_expires_at": _utc_now() - timedelta(seconds=1)})
    db.commit()
    assert _call(client, tokens["access_token"], "ping").status_code == 401


# --- the two logins do not open each other's door ---------------------------------------------------------------


def test_the_connector_refuses_a_call_without_signing_in(client):
    answer = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert answer.status_code == 401
    assert "oauth-protected-resource" in answer.headers["www-authenticate"]


def test_the_web_app_login_does_not_open_the_connector(client, auth_headers):
    answer = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers=auth_headers)
    assert answer.status_code == 401


def test_a_connector_token_does_not_open_the_rest_of_the_api(client, connect, user):
    tokens, _ = connect(user)
    answer = client.get("/categories", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert answer.status_code == 401
    answer = client.get("/connections", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert answer.status_code == 401


def test_tokens_are_kept_only_as_hashes(connect, user, db):
    tokens, _ = connect(user)
    grant = db.query(OAuthGrant).one()
    assert tokens["access_token"] not in (grant.access_hash, grant.refresh_hash)
    assert tokens["refresh_token"] not in (grant.access_hash, grant.refresh_hash)


# --- disconnecting -----------------------------------------------------------------------------------------------


def test_a_person_sees_their_connections_and_disconnects_one(client, connect, user, other_user, headers_for):
    tokens, _ = connect(user)
    other_tokens, _ = connect(other_user)
    shown = client.get("/connections", headers=headers_for(user)).json()["data"]
    assert [c["app"] for c in shown] == ["Claude"]
    assert client.delete(f"/connections/{shown[0]['id']}", headers=headers_for(user)).status_code == 204
    assert client.get("/connections", headers=headers_for(user)).json()["data"] == []
    assert _call(client, tokens["access_token"], "ping").status_code == 401
    assert _call(client, other_tokens["access_token"], "ping").status_code == 200  # the other person is untouched


def test_nobody_can_disconnect_someone_elses_connection(client, connect, user, other_user, headers_for):
    tokens, _ = connect(user)
    mine = client.get("/connections", headers=headers_for(user)).json()["data"][0]["id"]
    assert client.delete(f"/connections/{mine}", headers=headers_for(other_user)).status_code == 404
    assert _call(client, tokens["access_token"], "ping").status_code == 200
    assert client.get("/connections", headers=headers_for(other_user)).json()["data"] == []


def test_revoking_the_token_disconnects(client, connect, user):
    tokens, client_id = connect(user)
    client.post("/oauth/revoke", data={"token": tokens["refresh_token"], "client_id": client_id})
    assert _call(client, tokens["access_token"], "ping").status_code == 401


# --- the protocol ------------------------------------------------------------------------------------------------


def test_initialize_and_the_tool_list(client, connect, user):
    tokens, _ = connect(user)
    token = tokens["access_token"]
    started = _call(client, token, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
    assert started["protocolVersion"] == "2025-06-18" and "tools" in started["capabilities"]
    tools = _call(client, token, "tools/list").json()["result"]["tools"]
    # Narrow on purpose: one tool writes, and it can only add
    assert {t["name"] for t in tools} == {"list_categories", "preview_transactions", "add_transactions"}
    writers = [t["name"] for t in tools if not t["annotations"]["readOnlyHint"]]
    assert writers == ["add_transactions"]


def test_a_notification_gets_no_answer(client, connect, user):
    tokens, _ = connect(user)
    answer = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert answer.status_code == 202 and answer.content == b""


def test_unknown_tools_and_methods_are_refused(client, connect, user):
    token = connect(user)[0]["access_token"]
    assert _call(client, token, "tools/call", {"name": "delete_transaction", "arguments": {}}).json()["error"]
    assert _call(client, token, "resources/list").json()["error"]["code"] == -32601


def test_the_connector_does_not_stream(client):
    assert client.get("/mcp").status_code == 405


# --- the tools ---------------------------------------------------------------------------------------------------


def test_categories_are_the_familys_own_and_the_defaults(client, connect, user, other_user, db):
    db.add(Categories(name="Pets da família", family_id=user.family_id, group_id=_any_group(db)))
    db.add(Categories(name="Plantas do outro", family_id=other_user.family_id, group_id=_any_group(db)))
    db.commit()
    names = {c["name"] for c in _tool(client, connect(user)[0]["access_token"], "list_categories")["categories"]}
    assert "Pets da família" in names and "Supermercado" in names
    assert "Plantas do outro" not in names


def _any_group(db):
    from schemas.tables import CategoryGroups

    return db.query(CategoryGroups).first().id


def test_preview_saves_nothing_and_marks_what_exists(client, connect, user, make_transaction, category_id, db):
    make_transaction(user, category_id, label="Almoço", value=4500, when=datetime(2026, 3, 10, 12, 0))
    token = connect(user)[0]["access_token"]
    shown = _tool(client, token, "preview_transactions", {"rows": [_row(), _row(description="Jantar")]})
    assert shown["ok"] is True
    assert [r["status"] for r in shown["rows"]] == ["already_exists", "new"]
    assert shown["summary"] == {"new": 1, "already_exist": 1}
    assert shown["preview_id"]
    assert db.query(TransactionDB).count() == 1


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ({"date": (date.today() + timedelta(days=3)).isoformat()}, "future"),
        ({"date": "10/03/2026"}, "YYYY-MM-DD"),
        ({"date": "2026-02-30"}, "real day"),
        ({"amount_cents": -100}, "positive"),
        ({"amount_cents": 0}, "positive"),
        ({"amount_cents": 12.5}, "whole number"),
        ({"amount_cents": True}, "whole number"),
        ({"amount_cents": 2147483648}, "too large"),
        ({"type": "refund"}, "debit"),
        ({"category": "Não existe"}, "not one of the family"),
        ({"category": ""}, "required"),
        ({"description": ""}, "required"),
        ({"description": "x" * 101}, "maximum is 100"),
    ],
)
def test_preview_applies_the_import_rules(client, connect, user, bad, fragment):
    token = connect(user)[0]["access_token"]
    shown = _tool(client, token, "preview_transactions", {"rows": [_row(), _row(**bad)]})
    assert shown["ok"] is False and "preview_id" not in shown
    assert [p["row"] for p in shown["problems"]] == [2]
    assert fragment in shown["problems"][0]["problem"]


def test_a_category_of_another_family_is_unknown(client, connect, user, other_user, db):
    db.add(Categories(name="Plantas do outro", family_id=other_user.family_id, group_id=_any_group(db)))
    db.commit()
    token = connect(user)[0]["access_token"]
    shown = _tool(client, token, "preview_transactions", {"rows": [_row(category="Plantas do outro")]})
    assert shown["ok"] is False


def test_the_category_can_be_written_in_english_or_without_accents(client, connect, user):
    token = connect(user)[0]["access_token"]
    shown = _tool(client, token, "preview_transactions", {"rows": [_row(category="groceries")]})
    assert shown["ok"] is True and shown["rows"][0]["category"] == "Supermercado"


def test_too_many_rows_are_refused(client, connect, user):
    token = connect(user)[0]["access_token"]
    answer = _call(
        client, token, "tools/call", {"name": "preview_transactions", "arguments": {"rows": [_row()] * 201}}
    ).json()["result"]
    assert answer["isError"] is True
    answer = _call(client, token, "tools/call", {"name": "preview_transactions", "arguments": {"rows": []}}).json()[
        "result"
    ]
    assert answer["isError"] is True


def test_adding_needs_the_preview(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    refused = _tool(client, token, "add_transactions", {"rows": [_row()], "preview_id": "made-up"})
    assert refused["ok"] is False and "previewed" in refused["message"]
    assert db.query(TransactionDB).count() == 0


def test_only_the_previewed_rows_can_be_added(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    preview = _tool(client, token, "preview_transactions", {"rows": [_row()]})
    # A document that talked the AI into sending something else cannot reuse the preview of the confirmed rows
    changed = _tool(
        client,
        token,
        "add_transactions",
        {"rows": [_row(), _row(description="Extra", amount_cents=999999)], "preview_id": preview["preview_id"]},
    )
    assert changed["ok"] is False
    assert db.query(TransactionDB).count() == 0


def test_a_preview_from_one_person_does_not_work_for_another(client, connect, user, other_user, db):
    preview = _tool(client, connect(user)[0]["access_token"], "preview_transactions", {"rows": [_row()]})
    refused = _tool(
        client,
        connect(other_user)[0]["access_token"],
        "add_transactions",
        {"rows": [_row()], "preview_id": preview["preview_id"]},
    )
    assert refused["ok"] is False
    assert db.query(TransactionDB).count() == 0


def test_confirmed_rows_are_added_to_the_signed_in_persons_family(client, connect, make_user, user, other_user, db):
    partner = make_user("Partner", family=db.get(Families, user.family_id))
    token = connect(partner)[0]["access_token"]
    rows = [_row(), _row(description="Salário", amount_cents=500000, type="credit", category="groceries")]
    preview = _tool(client, token, "preview_transactions", {"rows": rows})
    added = _tool(client, token, "add_transactions", {"rows": rows, "preview_id": preview["preview_id"]})
    assert added == {"ok": True, "added": 2, "skipped_because_they_already_exist": 0}
    saved = db.query(TransactionDB).order_by(TransactionDB.label).all()
    assert [(t.label, t.value, t.type) for t in saved] == [("Almoço", 4500, "debit"), ("Salário", 500000, "credit")]
    assert {t.family_id for t in saved} == {user.family_id}
    assert {t.user_id for t in saved} == {partner.id}  # entered by the person who signed in, not by the account owner
    assert all(t.transactioned_at.date() == date(2026, 3, 10) for t in saved)
    assert db.query(TransactionDB).filter_by(family_id=other_user.family_id).count() == 0


def test_sending_the_same_statement_twice_adds_nothing_twice(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    rows = [_row(), _row(description="Jantar", amount_cents=8000)]
    first = _tool(client, token, "preview_transactions", {"rows": rows})
    _tool(client, token, "add_transactions", {"rows": rows, "preview_id": first["preview_id"]})
    second = _tool(client, token, "preview_transactions", {"rows": rows})
    assert [r["status"] for r in second["rows"]] == ["already_exists"] * 2
    again = _tool(client, token, "add_transactions", {"rows": rows, "preview_id": second["preview_id"]})
    assert again == {"ok": True, "added": 0, "skipped_because_they_already_exist": 2}
    assert db.query(TransactionDB).count() == 2


def test_two_equal_rows_in_one_statement_are_both_kept(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    rows = [_row(), _row()]  # two coffees on the same day for the same price
    preview = _tool(client, token, "preview_transactions", {"rows": rows})
    added = _tool(client, token, "add_transactions", {"rows": rows, "preview_id": preview["preview_id"]})
    assert added["added"] == 2


def test_an_invalid_row_means_nothing_is_added(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    preview = _tool(client, token, "preview_transactions", {"rows": [_row()]})
    refused = _tool(
        client,
        token,
        "add_transactions",
        {"rows": [_row(), _row(amount_cents=-5)], "preview_id": preview["preview_id"]},
    )
    assert refused["ok"] is False
    assert db.query(TransactionDB).count() == 0


def test_a_flood_of_calls_is_slowed_down(client, connect, user, monkeypatch):
    from api.routers import mcp_router

    monkeypatch.setattr(mcp_router, "CALLS_PER_MINUTE", 3)
    token = connect(user)[0]["access_token"]
    codes = [_call(client, token, "ping").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_a_huge_request_is_refused(client, connect, user):
    token = connect(user)[0]["access_token"]
    answer = client.post(
        "/mcp",
        content=b"x" * (1024 * 1024 + 10),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert answer.status_code == 413


# --- found in the security review --------------------------------------------------------------------------------


def test_a_preview_id_that_is_not_plain_ascii_is_refused_not_a_crash(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    for bad in ("é", "é.é", "123456789999.é", ".", "-1.x", "x" * 5000):
        refused = _tool(client, token, "add_transactions", {"rows": [_row()], "preview_id": bad})
        assert refused["ok"] is False
    assert db.query(TransactionDB).count() == 0


def test_a_preview_expires(client, connect, user, db, monkeypatch):
    from api.controllers import connector_controller

    token = connect(user)[0]["access_token"]
    preview = _tool(client, token, "preview_transactions", {"rows": [_row()]})
    real = connector_controller.utc_now
    monkeypatch.setattr(
        connector_controller, "utc_now", lambda: real() + timedelta(minutes=connector_controller.PREVIEW_MINUTES + 1)
    )
    refused = _tool(client, token, "add_transactions", {"rows": [_row()], "preview_id": preview["preview_id"]})
    assert refused["ok"] is False
    assert db.query(TransactionDB).count() == 0


def test_a_preview_id_cannot_be_given_a_later_expiry(client, connect, user, db):
    token = connect(user)[0]["access_token"]
    preview = _tool(client, token, "preview_transactions", {"rows": [_row()]})
    stamp, _, signature = preview["preview_id"].partition(".")
    forged = f"{int(stamp) + 86400}.{signature}"
    assert _tool(client, token, "add_transactions", {"rows": [_row()], "preview_id": forged})["ok"] is False


def test_a_person_can_add_only_so_many_transactions_an_hour(client, connect, user, db, monkeypatch):
    from api.controllers import connector_controller

    monkeypatch.setattr(connector_controller, "MAX_ROWS_PER_HOUR", 3)
    token = connect(user)[0]["access_token"]
    first = [_row(description=f"A{n}") for n in range(3)]
    preview = _tool(client, token, "preview_transactions", {"rows": first})
    assert _tool(client, token, "add_transactions", {"rows": first, "preview_id": preview["preview_id"]})["added"] == 3
    more = [_row(description="B")]
    preview = _tool(client, token, "preview_transactions", {"rows": more})
    refused = _tool(client, token, "add_transactions", {"rows": more, "preview_id": preview["preview_id"]})
    assert refused["ok"] is False and "an hour" in refused["message"]
    assert db.query(TransactionDB).count() == 3


def test_an_unexpected_error_in_a_tool_gives_a_generic_answer(client, connect, user, monkeypatch):
    from api.controllers import connector_controller

    def boom(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(connector_controller, "list_categories", boom)
    answer = _call(client, connect(user)[0]["access_token"], "tools/call", {"name": "list_categories"})
    assert answer.json()["error"]["code"] == -32603
    assert "secret detail" not in answer.text


def test_the_token_address_does_not_read_multipart_or_big_bodies(client, auth_headers):
    client_id = _register(client).json()["client_id"]
    code = _code_for(client, auth_headers, client_id)["code"][0]
    form = _token_form(client_id, code)
    refused = client.post("/oauth/token", files={k: (None, v) for k, v in form.items()})
    assert refused.status_code == 401 and refused.json()["error"] == "invalid_client"  # no field was read
    big = client.post(
        "/oauth/token", content=b"a=" + b"x" * 20000, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert big.status_code in (401, 413)
    assert client.post("/oauth/token", data=form).status_code == 200  # the code was not spent by the refused tries


def test_nothing_can_put_the_app_in_a_frame_and_the_connector_is_not_cached(client, connect, user):
    answer = client.get("/.well-known/oauth-authorization-server")
    assert answer.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in answer.headers["content-security-policy"]
    ping = _call(client, connect(user)[0]["access_token"], "ping")
    assert ping.headers["cache-control"] == "no-store"

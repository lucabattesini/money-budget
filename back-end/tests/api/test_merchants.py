"""Merchants (TKT-58): the place or company a transaction went to, as an optional setting of the family."""

import pytest

import graph.nodes as nodes
from agents.query.tools import query_tools
from agents.recorder.tools import recorder_tools
from graph.nodes import node_db_execute, node_recorder
from schemas.agents_schemas import ExpenseItem, RecorderResponse, ToolCall
from schemas.tables import Families, Merchants, TransactionDB


@pytest.fixture
def partner(make_user, db, user):
    return make_user("Partner", family=db.get(Families, user.family_id), role="member")


def _turn(client, headers, on=True):
    response = client.patch("/families/me/settings", json={"merchants_enabled": on}, headers=headers)
    assert response.status_code == 200
    return response


@pytest.fixture
def on(client, auth_headers):
    _turn(client, auth_headers, True)


def _create(client, headers, name):
    return client.post("/merchants", json={"name": name}, headers=headers)


def _names(client, headers):
    return [m["name"] for m in client.get("/merchants", headers=headers).json()["data"]]


def _spend(client, headers, category_id, **fields):
    body = {"label": "Corrida", "value": 1000, "category_id": category_id, **fields}
    return client.post("/transactions/create", json=body, headers=headers)


def _list(client, headers):
    return client.post("/transactions/", json={}, headers=headers).json()["data"]


# --- the setting ---------------------------------------------------------------------------------------------------


def test_merchants_are_off_until_the_family_turns_them_on(client, auth_headers):
    assert client.get("/families/me", headers=auth_headers).json()["data"]["merchants_enabled"] is False

    assert _turn(client, auth_headers, True).json()["data"]["merchants_enabled"] is True
    assert client.get("/families/me", headers=auth_headers).json()["data"]["merchants_enabled"] is True


def test_changing_another_setting_leaves_the_merchants_switch_alone(client, auth_headers, on):
    client.patch("/families/me/settings", json={"currency": "USD"}, headers=auth_headers)

    assert client.get("/families/me", headers=auth_headers).json()["data"]["merchants_enabled"] is True


def test_every_member_sees_the_switch(client, partner, headers_for, auth_headers, on):
    assert client.get("/families/me", headers=headers_for(partner)).json()["data"]["merchants_enabled"] is True


# --- managing merchants ----------------------------------------------------------------------------------------------


def test_a_merchant_is_created_listed_and_renamed(client, auth_headers):
    created = _create(client, auth_headers, "  Uber ")

    assert created.status_code == 201
    assert created.json()["data"] == {"id": created.json()["data"]["id"], "name": "Uber", "transactions": 0}
    renamed = client.patch(
        f"/merchants/{created.json()['data']['id']}", json={"name": "Uber Brasil"}, headers=auth_headers
    )
    assert renamed.status_code == 200
    assert _names(client, auth_headers) == ["Uber Brasil"]


@pytest.mark.parametrize("other", ["uber", "UBER", "🚗 Uber", "  uber  "])
def test_names_that_differ_only_by_case_accents_or_an_emoji_are_the_same_merchant(client, auth_headers, other):
    _create(client, auth_headers, "Uber")
    if other == "ÚBER":
        client.post(
            "/merchants", json={"name": "Úber"}, headers=auth_headers
        )  # a different set of accents is still same words

    response = _create(client, auth_headers, other)

    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um estabelecimento com esse nome."


def test_a_name_needs_words(client, auth_headers):
    assert _create(client, auth_headers, "   ").status_code == 422
    assert _create(client, auth_headers, "🚗").status_code == 422
    assert _create(client, auth_headers, "x" * 101).status_code == 422


def test_renaming_to_another_merchants_name_is_refused_but_to_its_own_words_is_fine(client, auth_headers):
    uber = _create(client, auth_headers, "Uber").json()["data"]
    _create(client, auth_headers, "iFood")

    assert client.patch(f"/merchants/{uber['id']}", json={"name": "ifood"}, headers=auth_headers).status_code == 409
    assert client.patch(f"/merchants/{uber['id']}", json={"name": "UBER"}, headers=auth_headers).status_code == 200


def test_the_list_counts_the_transactions_of_each_merchant(client, auth_headers, on, category_ids):
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="uber")
    _create(client, auth_headers, "iFood")

    rows = client.get("/merchants", headers=auth_headers).json()["data"]

    assert [(m["name"], m["transactions"]) for m in rows] == [("iFood", 0), ("Uber", 2)]


def test_a_merchant_that_transactions_use_cannot_be_deleted_and_one_that_nothing_uses_can(
    client, db, auth_headers, on, category_ids
):
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")
    unused = _create(client, auth_headers, "Netflix").json()["data"]
    [uber] = [m for m in client.get("/merchants", headers=auth_headers).json()["data"] if m["name"] == "Uber"]

    refused = client.delete(f"/merchants/{uber['id']}", headers=auth_headers)

    assert refused.status_code == 409
    assert "2 transações" in refused.json()["detail"]
    assert client.delete(f"/merchants/{unused['id']}", headers=auth_headers).status_code == 200
    assert _names(client, auth_headers) == ["Uber"]


def test_one_family_never_sees_or_changes_another_familys_merchants(client, db, auth_headers, other_user, headers_for):
    mine = _create(client, auth_headers, "Uber").json()["data"]
    theirs = _create(client, headers_for(other_user), "Uber").json()["data"]  # the same name in another family is fine

    assert _names(client, headers_for(other_user)) == ["Uber"]
    assert client.patch(f"/merchants/{theirs['id']}", json={"name": "x"}, headers=auth_headers).status_code == 404
    assert client.delete(f"/merchants/{theirs['id']}", headers=auth_headers).status_code == 404
    assert [m.name for m in db.query(Merchants).filter_by(id=mine["id"])] == ["Uber"]


def test_merchants_need_a_login(client):
    assert client.get("/merchants").status_code == 401
    assert client.post("/merchants", json={"name": "x"}).status_code == 401


# --- transactions with a merchant ----------------------------------------------------------------------------------------


def test_a_transaction_can_name_a_new_merchant_and_the_next_one_reuses_it(client, db, auth_headers, on, category_ids):
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="🚗 uber")

    assert db.query(Merchants).count() == 1
    listed = _list(client, auth_headers)
    assert {t["merchant_id"] for t in listed} == {db.query(Merchants).one().id}


def test_a_transaction_without_a_merchant_stays_valid(client, db, auth_headers, on, category_ids):
    assert _spend(client, auth_headers, category_ids["Sem categoria"]).status_code == 201

    assert db.query(TransactionDB).one().merchant_id is None


def test_naming_a_merchant_while_they_are_off_is_refused_and_nothing_is_saved(client, db, auth_headers, category_ids):
    response = _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")

    assert response.status_code == 409
    assert (db.query(TransactionDB).count(), db.query(Merchants).count()) == (0, 0)


def test_update_changes_keeps_and_removes_the_merchant(
    client, db, user, auth_headers, on, category_ids, make_transaction
):
    row = make_transaction(user, category_ids["Sem categoria"])

    def put(**fields):
        return client.put(
            f"/transactions/{row.id}",
            json={"label": "Corrida", "value": 1000, "category_id": category_ids["Sem categoria"], **fields},
            headers=auth_headers,
        )

    assert put(merchant="Uber").status_code == 200
    db.refresh(row)
    uber = row.merchant_id
    assert uber is not None
    assert put(label="Outra").status_code == 200  # left out: kept
    db.refresh(row)
    assert row.merchant_id == uber
    assert put(merchant="").status_code == 200  # empty: taken off
    db.refresh(row)
    assert row.merchant_id is None


def test_turning_merchants_off_hides_them_but_keeps_the_data_and_turning_them_on_brings_it_back(
    client, db, auth_headers, on, category_ids
):
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")

    _turn(client, auth_headers, False)
    assert db.query(Merchants).count() == 1
    assert db.query(TransactionDB).one().merchant_id is not None
    _turn(client, auth_headers, True)

    assert _names(client, auth_headers) == ["Uber"]
    assert _list(client, auth_headers)[0]["merchant_id"] is not None


# --- joining a family with the data ------------------------------------------------------------------------------------------


def test_bringing_the_data_when_joining_brings_the_merchants_and_merges_the_same_names(
    client, db, user, other_user, auth_headers, headers_for, category_ids, make_transaction
):
    mine = Merchants(family_id=user.family_id, name="Uber")
    joiners_same = Merchants(family_id=other_user.family_id, name="🚗 uber")
    joiners_own = Merchants(family_id=other_user.family_id, name="Netflix")
    db.add_all([mine, joiners_same, joiners_own])
    db.commit()
    for merchant in (joiners_same, joiners_own):
        make_transaction(other_user, category_ids["Sem categoria"], label=merchant.name).merchant_id = merchant.id
    db.commit()
    code = client.post("/families/invites", headers=auth_headers).json()["data"]["code"]

    client.post("/families/join", json={"code": code, "bring_data": True}, headers=headers_for(other_user))

    db.expire_all()
    family_merchants = db.query(Merchants).filter_by(family_id=user.family_id).all()
    assert sorted(m.name for m in family_merchants) == ["Netflix", "Uber"]
    assert db.query(Merchants).count() == 2
    by_label = {t["label"]: t["merchant_id"] for t in _list(client, auth_headers)}
    assert by_label["🚗 uber"] == mine.id  # merged into the family's own
    assert by_label["Netflix"] == joiners_own.id


# --- the assistant ---------------------------------------------------------------------------------------------------------------


def _record(user, items, monkeypatch):
    monkeypatch.setattr(nodes, "run_recorder", lambda message, **kw: RecorderResponse(items=items))
    return node_recorder({"user_message": "x", "user_id": user.id, "family_id": user.family_id})


def test_the_assistant_records_the_merchant_only_while_the_family_has_merchants_on(
    client, db, user, auth_headers, monkeypatch
):
    item = ExpenseItem(amount=10, category="Sem categoria", description="Corrida", merchant="Uber")

    _record(user, [item], monkeypatch)  # off: the merchant is ignored, nothing fails
    assert (db.query(TransactionDB).one().merchant_id, db.query(Merchants).count()) == (None, 0)

    _turn(client, auth_headers, True)
    _record(user, [item], monkeypatch)
    assert db.query(Merchants).one().name == "Uber"
    assert db.query(TransactionDB).order_by(TransactionDB.id.desc()).first().merchant_id == db.query(Merchants).one().id


def test_the_assistant_is_only_given_merchants_while_they_are_on():
    def merchant_in_recorder(tools):
        return (
            "merchant" in tools["function_declarations"][0]["parameters"]["properties"]["items"]["items"]["properties"]
        )

    assert not merchant_in_recorder(recorder_tools(False))
    assert merchant_in_recorder(recorder_tools(True))
    off, on_ = query_tools(False), query_tools(True)
    assert all("merchants" not in d["parameters"]["properties"] for d in off["function_declarations"])
    assert all("merchants" in d["parameters"]["properties"] for d in on_["function_declarations"])
    summarize = on_["function_declarations"][1]["parameters"]["properties"]["group_by"]["enum"]
    assert "merchant" in summarize
    assert "merchant" not in off["function_declarations"][1]["parameters"]["properties"]["group_by"]["enum"]


def _ask(user, call):
    [result] = node_db_execute({"user_id": user.id, "family_id": user.family_id, "query_tool_calls": [call]})[
        "db_results"
    ]
    return result["result"]


def test_the_assistant_can_total_and_filter_by_merchant_while_they_are_on(
    client, db, user, auth_headers, on, category_ids, monkeypatch
):
    for merchant, value in (("Uber", 1000), ("Uber", 500), ("iFood", 2000)):
        _spend(client, auth_headers, category_ids["Sem categoria"], merchant=merchant, value=value)

    grouped = _ask(user, ToolCall(name="summarize_transactions", args={"group_by": "merchant"}))
    only_uber = _ask(user, ToolCall(name="summarize_transactions", args={"merchants": ["uber"]}))
    listed = _ask(user, ToolCall(name="list_transactions", args={"merchants": ["Uber"]}))

    assert [(g["merchant"], g["total"]) for g in grouped] == [("iFood", 20.0), ("Uber", 15.0)]
    assert only_uber[0]["total"] == 15.0
    assert {row["merchant"] for row in listed} == {"Uber"}


def test_a_merchant_the_family_does_not_have_matches_nothing_and_off_ignores_the_filter(
    client, db, user, auth_headers, on, category_ids
):
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Uber")

    nothing = _ask(user, ToolCall(name="summarize_transactions", args={"merchants": ["Netflix"]}))
    _turn(client, auth_headers, False)
    everything = _ask(user, ToolCall(name="list_transactions", args={"merchants": ["Netflix"]}))

    assert nothing[0]["count"] == 0
    assert len(everything) == 1 and "merchant" not in everything[0]


def test_one_family_cannot_filter_by_another_familys_merchant(
    client, db, user, other_user, auth_headers, headers_for, on, category_ids
):
    _turn(client, headers_for(other_user), True)
    _spend(client, headers_for(other_user), category_ids["Sem categoria"], merchant="Uber")
    _spend(client, auth_headers, category_ids["Sem categoria"], merchant="Padaria")

    result = _ask(user, ToolCall(name="summarize_transactions", args={"merchants": ["Uber"]}))

    assert result[0]["count"] == 0

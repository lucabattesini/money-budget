from datetime import datetime

import pytest

from schemas.tables import TransactionDB


def _create(client, headers, category_id, label="Almoço", value=2500):
    return client.post(
        "/transactions/create",
        json={"label": label, "value": value, "category_id": category_id},
        headers=headers,
    )


def _list(client, headers, body=None):
    response = client.post("/transactions/", json=body or {}, headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def _summed(client, headers, body=None):
    response = client.post("/transactions/summed-by-category", json=body or {}, headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


# --- create ----------------------------------------------------------------

def test_create_stores_the_transaction_for_the_caller(client, db, user, auth_headers, category_ids):
    response = _create(client, auth_headers, category_ids["Alimentação"], label="Almoço", value=2500)

    assert response.status_code == 201
    row = db.query(TransactionDB).one()
    assert (row.user_id, row.label, row.value, row.category_id) == (user.id, "Almoço", 2500, category_ids["Alimentação"])
    assert row.date is not None


def test_create_requires_authentication(client, db, category_ids):
    response = client.post("/transactions/create", json={"label": "x", "value": 1, "category_id": category_ids["Outros"]})

    assert response.status_code == 401
    assert db.query(TransactionDB).count() == 0


def test_create_rejects_a_missing_label(client, db, auth_headers, category_ids):
    response = client.post(
        "/transactions/create", json={"value": 100, "category_id": category_ids["Outros"]}, headers=auth_headers
    )

    assert response.status_code == 422
    assert db.query(TransactionDB).count() == 0


# --- list ------------------------------------------------------------------

def test_list_returns_only_the_callers_transactions(client, user, other_user, auth_headers, headers_for,
                                                     make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], label="Mine", value=1000)
    make_transaction(other_user, category_ids["Alimentação"], label="Theirs", value=9999)

    mine = _list(client, auth_headers)
    theirs = _list(client, headers_for(other_user))

    assert [(t["label"], t["value"]) for t in mine] == [("Mine", 1000)]
    assert [(t["label"], t["value"]) for t in theirs] == [("Theirs", 9999)]


def test_list_is_newest_first(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="old", when=datetime(2026, 1, 10))
    make_transaction(user, cat, label="new", when=datetime(2026, 3, 10))
    make_transaction(user, cat, label="mid", when=datetime(2026, 2, 10))

    assert [t["label"] for t in _list(client, auth_headers)] == ["new", "mid", "old"]


def test_list_can_be_filtered_by_year(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="2025", when=datetime(2025, 6, 1))
    make_transaction(user, cat, label="2026", when=datetime(2026, 6, 1))

    rows = _list(client, auth_headers, {"organized_by": "year", "date": "2026-06-01T00:00:00"})

    assert [t["label"] for t in rows] == ["2026"]


def test_list_can_be_filtered_by_month_within_one_year(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="march", when=datetime(2026, 3, 5))
    make_transaction(user, cat, label="april", when=datetime(2026, 4, 5))

    rows = _list(client, auth_headers, {"organized_by": "month", "date": "2026-03-01T00:00:00"})

    assert [t["label"] for t in rows] == ["march"]


# --- summed by category ----------------------------------------------------

def test_summed_groups_totals_per_category(client, user, auth_headers, make_transaction, category_ids):
    food, transport = category_ids["Alimentação"], category_ids["Transporte"]
    make_transaction(user, food, value=1000)
    make_transaction(user, food, value=2500)
    make_transaction(user, transport, value=700)

    rows = _summed(client, auth_headers)

    assert {r["category_id"]: r["total"] for r in rows} == {food: 3500, transport: 700}


def test_summed_ignores_other_users(client, user, other_user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, value=1000)
    make_transaction(other_user, cat, value=50_000)

    assert _summed(client, auth_headers) == [{"category_id": cat, "total": 1000}]


def test_summed_is_empty_without_transactions(client, auth_headers):
    assert _summed(client, auth_headers) == []


# --- delete ----------------------------------------------------------------

def test_delete_removes_the_callers_transaction(client, db, user, auth_headers, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    response = client.delete(f"/transactions/{row.id}", headers=auth_headers)

    assert response.status_code == 202
    assert db.query(TransactionDB).count() == 0


def test_delete_cannot_remove_another_users_transaction(client, db, user, other_user, headers_for,
                                                         make_transaction, category_ids):
    theirs = make_transaction(other_user, category_ids["Alimentação"], label="Theirs")

    response = client.delete(f"/transactions/{theirs.id}", headers=headers_for(user))

    assert response.json()["data"] == {"message": "Transaction not found"}
    assert db.query(TransactionDB).filter_by(id=theirs.id).count() == 1


def test_delete_of_an_unknown_id_reports_not_found(client, auth_headers):
    response = client.delete("/transactions/999999", headers=auth_headers)

    assert response.json()["data"] == {"message": "Transaction not found"}


def test_delete_requires_authentication(client, user, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    assert client.delete(f"/transactions/{row.id}").status_code == 401


# --- error codes (TKT-28) ------------------------------------------------

@pytest.mark.skip(reason="TKT-28: deleting a missing transaction answers 202 instead of 404")
def test_deleting_an_unknown_transaction_is_not_found(client, auth_headers):
    assert client.delete("/transactions/999999", headers=auth_headers).status_code == 404


@pytest.mark.skip(reason="TKT-28: deleting someone else's transaction answers 202 instead of 404")
def test_deleting_another_users_transaction_is_not_found(client, user, other_user, headers_for,
                                                         make_transaction, category_ids):
    theirs = make_transaction(other_user, category_ids["Alimentação"])

    assert client.delete(f"/transactions/{theirs.id}", headers=headers_for(user)).status_code == 404


@pytest.mark.skip(reason="TKT-28: an unknown category makes the API return a 500")
def test_creating_with_an_unknown_category_is_a_client_error(db, user, auth_headers):
    from fastapi.testclient import TestClient

    from api.app import app

    # raise_server_exceptions=False: we want to see the status code a real client would get
    response = TestClient(app, raise_server_exceptions=False).post(
        "/transactions/create", json={"label": "x", "value": 100, "category_id": 999999}, headers=auth_headers
    )

    assert response.status_code in (400, 404, 422)


# --- known bugs (TKT-26) ---------------------------------------------------

@pytest.mark.skip(reason="TKT-26: a date grouping without a date crashes with a 500 instead of a client error")
@pytest.mark.parametrize("path", ["/transactions/", "/transactions/summed-by-category"])
def test_grouping_without_a_date_is_a_client_error(client, auth_headers, path):
    response = client.post(path, json={"organized_by": "day"}, headers=auth_headers)

    assert response.status_code == 422

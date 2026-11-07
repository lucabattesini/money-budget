from datetime import datetime

from schemas.tables import Families, Merchants, TransactionDB
from tests.conftest import MISSING_ID


def _ids(*rows):
    return [str(r.id) for r in rows]


def _reload(db, *rows):
    db.expire_all()
    return [db.get(TransactionDB, r.id) for r in rows]


# --- bulk update -------------------------------------------------------------


def test_bulk_update_changes_the_category_and_excluded_of_every_selected(
    client, db, user, auth_headers, make_transaction, category_ids
):
    a = make_transaction(user, category_ids["Sem categoria"], label="a")
    b = make_transaction(user, category_ids["Sem categoria"], label="b")
    untouched = make_transaction(user, category_ids["Sem categoria"], label="c")

    response = client.post(
        "/transactions/bulk-update",
        json={"ids": _ids(a, b), "category_id": str(category_ids["Supermercado"]), "excluded": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"updated": 2}
    a, b, untouched = _reload(db, a, b, untouched)
    assert (a.category_id, a.excluded, b.category_id, b.excluded) == (
        category_ids["Supermercado"],
        True,
        category_ids["Supermercado"],
        True,
    )
    assert a.updated_at is not None
    assert (untouched.category_id, untouched.excluded, untouched.updated_at) == (
        category_ids["Sem categoria"],
        False,
        None,
    )


def test_bulk_update_keeps_what_was_not_asked_to_change(client, db, user, auth_headers, make_transaction, category_ids):
    t = make_transaction(user, category_ids["Sem categoria"], label="Mercado", value=1234, excluded=True)

    client.post(
        "/transactions/bulk-update",
        json={"ids": _ids(t), "category_id": str(category_ids["Supermercado"])},
        headers=auth_headers,
    )

    (t,) = _reload(db, t)
    assert (t.label, t.value, t.excluded, t.user_id) == ("Mercado", 1234, True, user.id)


def test_bulk_update_changes_who_paid(client, db, user, make_user, auth_headers, make_transaction, category_ids):
    other = make_user("Bia", family=db.get(Families, user.family_id))
    t = make_transaction(user, category_ids["Sem categoria"])

    response = client.post(
        "/transactions/bulk-update", json={"ids": _ids(t), "user_id": str(other.id)}, headers=auth_headers
    )

    assert response.status_code == 200
    assert _reload(db, t)[0].user_id == other.id


def test_bulk_update_refuses_a_person_from_another_family_and_changes_nothing(
    client, db, user, other_user, auth_headers, make_transaction, category_ids
):
    t = make_transaction(user, category_ids["Sem categoria"])

    response = client.post(
        "/transactions/bulk-update", json={"ids": _ids(t), "user_id": str(other_user.id)}, headers=auth_headers
    )

    assert response.status_code == 404
    assert _reload(db, t)[0].user_id == user.id


def test_bulk_update_with_one_foreign_id_changes_nothing(
    client, db, user, other_user, auth_headers, make_transaction, category_ids
):
    mine = make_transaction(user, category_ids["Sem categoria"])
    theirs = make_transaction(other_user, category_ids["Sem categoria"])

    response = client.post(
        "/transactions/bulk-update",
        json={"ids": _ids(mine, theirs), "category_id": str(category_ids["Supermercado"])},
        headers=auth_headers,
    )

    assert response.status_code == 404
    mine, theirs = _reload(db, mine, theirs)
    assert mine.category_id == theirs.category_id == category_ids["Sem categoria"]


def test_bulk_update_with_a_missing_id_looks_the_same_as_a_foreign_one(client, user, auth_headers, category_ids):
    response = client.post(
        "/transactions/bulk-update",
        json={"ids": [str(MISSING_ID)], "excluded": True},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_bulk_update_refuses_an_unknown_category(client, db, user, auth_headers, make_transaction, category_ids):
    t = make_transaction(user, category_ids["Sem categoria"])

    response = client.post(
        "/transactions/bulk-update", json={"ids": _ids(t), "category_id": str(MISSING_ID)}, headers=auth_headers
    )

    assert response.status_code == 404
    assert _reload(db, t)[0].category_id == category_ids["Sem categoria"]


def test_bulk_update_needs_something_to_change_and_some_ids(client, user, auth_headers, make_transaction, category_ids):
    t = make_transaction(user, category_ids["Sem categoria"])

    assert client.post("/transactions/bulk-update", json={"ids": _ids(t)}, headers=auth_headers).status_code == 422
    assert (
        client.post("/transactions/bulk-update", json={"ids": [], "excluded": True}, headers=auth_headers).status_code
        == 422
    )


def test_bulk_update_sets_and_removes_the_merchant(client, db, user, auth_headers, make_transaction, category_ids):
    db.get(Families, user.family_id).merchants_enabled = True
    db.commit()
    a = make_transaction(user, category_ids["Sem categoria"], label="a")
    b = make_transaction(user, category_ids["Sem categoria"], label="b")

    client.post("/transactions/bulk-update", json={"ids": _ids(a, b), "merchant": "Uber"}, headers=auth_headers)

    a, b = _reload(db, a, b)
    merchant = db.query(Merchants).one()
    assert (merchant.name, a.merchant_id, b.merchant_id) == ("Uber", merchant.id, merchant.id)

    client.post("/transactions/bulk-update", json={"ids": _ids(a), "merchant": ""}, headers=auth_headers)
    a, b = _reload(db, a, b)
    assert (a.merchant_id, b.merchant_id) == (None, merchant.id)


def test_bulk_update_refuses_a_merchant_while_merchants_are_off(
    client, db, user, auth_headers, make_transaction, category_ids
):
    t = make_transaction(user, category_ids["Sem categoria"])

    response = client.post("/transactions/bulk-update", json={"ids": _ids(t), "merchant": "Uber"}, headers=auth_headers)

    assert response.status_code == 409
    assert db.query(Merchants).count() == 0


def test_bulk_update_requires_authentication(client):
    assert (
        client.post("/transactions/bulk-update", json={"ids": [str(MISSING_ID)], "excluded": True}).status_code == 401
    )


# --- bulk delete -------------------------------------------------------------


def test_bulk_delete_removes_only_the_selected(client, db, user, auth_headers, make_transaction, category_ids):
    a = make_transaction(user, category_ids["Sem categoria"], label="a")
    b = make_transaction(user, category_ids["Sem categoria"], label="b")
    keep = make_transaction(user, category_ids["Sem categoria"], label="keep")

    response = client.post("/transactions/bulk-delete", json={"ids": _ids(a, b)}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": 2}
    assert [t.label for t in db.query(TransactionDB).all()] == ["keep"]
    assert keep.id == db.query(TransactionDB).one().id


def test_bulk_delete_never_touches_another_familys_transactions(
    client, db, user, other_user, auth_headers, make_transaction, category_ids
):
    mine = make_transaction(user, category_ids["Sem categoria"])
    theirs = make_transaction(other_user, category_ids["Sem categoria"])

    response = client.post("/transactions/bulk-delete", json={"ids": _ids(mine, theirs)}, headers=auth_headers)

    assert response.status_code == 404
    assert db.query(TransactionDB).count() == 2


def test_bulk_delete_requires_authentication_and_ids(client, auth_headers):
    assert client.post("/transactions/bulk-delete", json={"ids": [str(MISSING_ID)]}).status_code == 401
    assert client.post("/transactions/bulk-delete", json={"ids": []}, headers=auth_headers).status_code == 422


# --- duplicates --------------------------------------------------------------


def _duplicates(client, headers, start, end):
    return client.post("/transactions/duplicates", json={"start_date": start, "end_date": end}, headers=headers)


def test_duplicates_groups_same_day_amount_and_type(client, db, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    first = make_transaction(user, cat, label="Padaria", value=1000, when=datetime(2026, 3, 10, 9, 0))
    second = make_transaction(user, cat, label="PADARIA SP", value=1000, when=datetime(2026, 3, 10, 18, 30))
    first.created_at, second.created_at = datetime(2026, 3, 10, 10, 0), datetime(2026, 3, 10, 11, 0)
    second.created_at, first.created_at = (
        datetime(2026, 3, 10, 12, 0),
        datetime(2026, 3, 10, 11, 0),
    )  # saved out of order on purpose
    db.commit()
    make_transaction(user, cat, value=1000, when=datetime(2026, 3, 11, 9, 0))  # another day
    make_transaction(user, cat, value=1001, when=datetime(2026, 3, 10, 9, 0))  # another amount
    make_transaction(user, cat, value=1000, when=datetime(2026, 3, 10, 9, 0), type="credit")  # another type

    response = _duplicates(client, auth_headers, "2026-03-01", "2026-03-31")

    assert response.status_code == 200
    groups = response.json()["data"]
    assert len(groups) == 1
    assert [t["id"] for t in groups[0]] == [str(first.id), str(second.id)]  # the one saved first comes first
    assert groups[0][0]["category_name"] and groups[0][0]["value"] == 1000


def test_duplicates_only_looks_inside_the_range_including_both_end_days(
    client, user, auth_headers, make_transaction, category_ids
):
    cat = category_ids["Sem categoria"]
    for day in (9, 10, 20, 20):
        make_transaction(user, cat, value=500, when=datetime(2026, 3, day, 23, 59))
    make_transaction(user, cat, value=700, when=datetime(2026, 3, 31, 23, 59))
    make_transaction(user, cat, value=700, when=datetime(2026, 4, 1, 0, 0))  # first day after the range

    assert _duplicates(client, auth_headers, "2026-03-10", "2026-03-19").json()["data"] == []
    assert [len(g) for g in _duplicates(client, auth_headers, "2026-03-10", "2026-03-20").json()["data"]] == [2]
    assert [len(g) for g in _duplicates(client, auth_headers, "2026-03-20", "2026-03-20").json()["data"]] == [2]
    # 31 March and 1 April are different days, so they are not duplicates of each other
    assert [len(g) for g in _duplicates(client, auth_headers, "2026-03-31", "2026-04-01").json()["data"]] == []


def test_duplicates_ignores_other_familys_rows(client, user, other_user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, value=500, when=datetime(2026, 3, 10, 9, 0))
    make_transaction(other_user, cat, value=500, when=datetime(2026, 3, 10, 9, 0))

    assert _duplicates(client, auth_headers, "2026-03-01", "2026-03-31").json()["data"] == []


def test_duplicates_counts_members_of_the_same_family_together(
    client, db, user, make_user, auth_headers, make_transaction, category_ids
):
    other = make_user("Bia", family=db.get(Families, user.family_id))
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, value=500, when=datetime(2026, 3, 10, 9, 0))
    make_transaction(other, cat, value=500, when=datetime(2026, 3, 10, 9, 0))

    assert len(_duplicates(client, auth_headers, "2026-03-01", "2026-03-31").json()["data"]) == 1


def test_duplicates_validates_the_range_and_login(client, auth_headers):
    assert _duplicates(client, auth_headers, "2026-03-31", "2026-03-01").status_code == 422
    assert (
        client.post("/transactions/duplicates", json={"start_date": "2026-03-01"}, headers=auth_headers).status_code
        == 422
    )
    assert (
        client.post("/transactions/duplicates", json={"start_date": "2026-03-01", "end_date": "2026-03-02"}).status_code
        == 401
    )

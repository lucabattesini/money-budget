"""Data belongs to a family, not to a person (TKT-42).

`user` and `other_user` are in different families. `partner` below is a second person in `user`'s family: the
sign-up flow does not create such a person yet (inviting is TKT-43), so the tests put them there directly.
"""

import pytest

import graph.nodes as nodes
from api.controllers import auth_controller
from graph.nodes import node_recorder
from schemas.agents_schemas import ExpenseItem, RecorderResponse
from schemas.tables import Categories, ExportJobDB, TransactionDB, Users


@pytest.fixture
def partner(make_user, user):
    class _Family:
        id = user.family_id

    return make_user("Partner", family=_Family)


@pytest.fixture
def private_category(db, other_user):
    row = Categories(name="Pets", family_id=other_user.family_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --- who is in which family -----------------------------------------------------------------


def test_a_new_user_gets_a_family_of_their_own_on_the_first_login_and_keeps_it(client, db, monkeypatch):
    payload = {"sub": "g-new", "name": "New", "email": "new@example.com"}
    monkeypatch.setattr(auth_controller.id_token, "verify_oauth2_token", lambda *a, **k: dict(payload))

    client.post("/auth/google", json={"id_token": "t"})
    first = db.query(Users).filter_by(google_id="g-new").one().family_id
    client.post("/auth/google", json={"id_token": "t"})

    assert db.query(Users).filter_by(family_id=first).count() == 1
    assert db.query(Users).filter_by(google_id="g-new").one().family_id == first


def test_two_new_users_never_share_a_family(user, other_user):
    assert user.family_id != other_user.family_id


def test_a_token_of_a_user_that_no_longer_exists_is_unauthorized(client, db, user, auth_headers):
    db.delete(user)
    db.commit()

    assert client.post("/transactions/", json={}, headers=auth_headers).status_code == 401


# --- people of one family share the budget ---------------------------------------------------


def test_a_family_member_sees_what_another_member_entered_and_who_entered_it(
    client, db, user, partner, auth_headers, headers_for, category_ids
):
    created = client.post(
        "/transactions/create",
        json={"label": "Mercado", "value": 5000, "category_id": category_ids["Supermercado"]},
        headers=auth_headers,
    )
    assert created.status_code == 201

    listed = client.post("/transactions/", json={}, headers=headers_for(partner)).json()["data"]

    assert [t["label"] for t in listed] == ["Mercado"]
    row = db.query(TransactionDB).one()
    assert (row.family_id, row.user_id) == (user.family_id, user.id)


def test_a_family_member_can_edit_and_delete_what_another_member_entered(
    client, db, user, partner, headers_for, make_transaction, category_ids
):
    row = make_transaction(user, category_ids["Restaurantes e Bares"], label="Almoço", value=1000)

    edited = client.put(
        f"/transactions/{row.id}",
        json={"label": "Jantar", "value": 2000, "category_id": category_ids["Restaurantes e Bares"]},
        headers=headers_for(partner),
    )
    assert edited.status_code == 200
    db.expire_all()
    assert db.get(TransactionDB, row.id).user_id == user.id  # editing does not change the author

    assert client.delete(f"/transactions/{row.id}", headers=headers_for(partner)).status_code == 202
    assert db.query(TransactionDB).count() == 0


def test_the_summary_adds_up_the_whole_family(client, user, partner, auth_headers, make_transaction, category_ids):
    make_transaction(user, category_ids["Sem categoria"], value=1000)
    make_transaction(partner, category_ids["Sem categoria"], value=500)

    response = client.post("/transactions/summed-by-category", json={}, headers=auth_headers)

    assert response.json()["data"] == [{"category_id": category_ids["Sem categoria"], "total": 1500}]


# --- another family sees and changes nothing -------------------------------------------------


def test_another_family_cannot_see_edit_or_delete_a_transaction(
    client, db, user, other_user, headers_for, make_transaction, category_ids
):
    row = make_transaction(user, category_ids["Restaurantes e Bares"], label="Private", value=1000)
    stranger = headers_for(other_user)

    assert client.post("/transactions/", json={}, headers=stranger).json()["data"] == []
    edit = client.put(
        f"/transactions/{row.id}",
        json={"label": "Hacked", "value": 1, "category_id": category_ids["Sem categoria"]},
        headers=stranger,
    )
    delete = client.delete(f"/transactions/{row.id}", headers=stranger)
    missing = client.delete("/transactions/999999", headers=stranger)

    assert (edit.status_code, delete.status_code) == (404, 404)
    assert edit.json() == missing.json()  # a foreign id looks exactly like a missing one
    assert delete.json() == missing.json()
    db.expire_all()
    saved = db.get(TransactionDB, row.id)
    assert (saved.label, saved.value) == ("Private", 1000)


def test_another_family_cannot_use_a_category_that_is_not_theirs(
    client, db, user, auth_headers, headers_for, other_user, make_transaction, private_category, category_ids
):
    row = make_transaction(user, category_ids["Restaurantes e Bares"])

    create = client.post(
        "/transactions/create",
        json={"label": "x", "value": 100, "category_id": private_category.id},
        headers=auth_headers,
    )
    update = client.put(
        f"/transactions/{row.id}",
        json={"label": "x", "value": 100, "category_id": private_category.id},
        headers=auth_headers,
    )
    unknown = client.post(
        "/transactions/create", json={"label": "x", "value": 100, "category_id": 999999}, headers=auth_headers
    )

    assert (create.status_code, update.status_code) == (404, 404)
    assert create.json() == unknown.json()
    db.expire_all()
    assert db.get(TransactionDB, row.id).category_id == category_ids["Restaurantes e Bares"]
    # ...while its owners can use it
    ok = client.post(
        "/transactions/create",
        json={"label": "x", "value": 100, "category_id": private_category.id},
        headers=headers_for(other_user),
    )
    assert ok.status_code == 201


# --- exports ---------------------------------------------------------------------------------


@pytest.fixture
def export_queue(monkeypatch):
    from api.controllers import exports_controller
    from api.routers import exports_router

    pending = []
    monkeypatch.setattr(exports_router, "run_export_job", pending.append)

    def run():
        while pending:
            exports_controller.run_export_job(pending.pop(0))

    return run


def test_an_export_holds_the_whole_family_and_nobody_elses(
    client, user, partner, other_user, auth_headers, headers_for, make_transaction, category_ids, export_queue
):
    make_transaction(user, category_ids["Sem categoria"], label="Mine")
    make_transaction(partner, category_ids["Sem categoria"], label="Partner's")
    make_transaction(other_user, category_ids["Sem categoria"], label="Stranger's")
    job_id = client.post("/exports", json={"format": "csv"}, headers=auth_headers).json()["data"]["id"]
    export_queue()

    text = client.get(f"/exports/{job_id}/file", headers=auth_headers).content.decode("utf-8-sig")

    assert "Mine" in text and "Partner's" in text
    assert "Stranger's" not in text


def test_an_export_file_is_only_offered_to_the_person_who_asked_even_inside_the_family(
    client, db, user, partner, auth_headers, headers_for, export_queue
):
    job_id = client.post("/exports", json={"format": "csv"}, headers=auth_headers).json()["data"]["id"]
    export_queue()

    assert client.get(f"/exports/{job_id}", headers=headers_for(partner)).status_code == 404
    assert client.get(f"/exports/{job_id}/file", headers=headers_for(partner)).status_code == 404
    assert client.get(f"/exports/{job_id}/file", headers=auth_headers).status_code == 200
    job = db.get(ExportJobDB, job_id)
    assert (job.family_id, job.requested_by) == (user.family_id, user.id)


def test_a_family_has_one_export_at_a_time(client, user, partner, auth_headers, headers_for, other_user, export_queue):
    assert client.post("/exports", json={"format": "csv"}, headers=auth_headers).status_code == 202

    blocked = client.post("/exports", json={"format": "csv"}, headers=headers_for(partner))
    assert blocked.status_code == 409
    assert "família" in blocked.json()["detail"]  # says whose export is running, not "you already have one"
    assert client.post("/exports", json={"format": "csv"}, headers=headers_for(other_user)).status_code == 202


# --- the WhatsApp assistant ------------------------------------------------------------------


def _record(user, items):
    return node_recorder({"user_message": "x", "user_id": user.id, "family_id": user.family_id})


def test_the_assistant_saves_in_the_speakers_family_and_remembers_who_spoke(
    db, user, partner, other_user, monkeypatch, category_ids
):
    reply = RecorderResponse(items=[ExpenseItem(amount=10.0, category="Sem categoria", description="Café")])
    monkeypatch.setattr(nodes, "run_recorder", lambda message: reply)

    _record(partner, None)

    [row] = db.query(TransactionDB).all()
    assert (row.family_id, row.user_id) == (user.family_id, partner.id)
    assert row.family_id != other_user.family_id


def test_the_assistant_cannot_file_an_expense_under_another_familys_category(
    db, user, other_user, private_category, monkeypatch, category_ids
):
    reply = RecorderResponse(items=[ExpenseItem(amount=10.0, category="Pets", description="Ração")])
    monkeypatch.setattr(nodes, "run_recorder", lambda message: reply)

    _record(user, None)

    [row] = db.query(TransactionDB).all()
    assert row.category_id == category_ids["Sem categoria"]  # unknown to this family, so it falls back

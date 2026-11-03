"""Inviting people to a family and joining it with a code (TKT-43).

`user` is alone in their own family and `other_user` in another one. In most tests `other_user` is the person
who joins `user`'s family.
"""

import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func

from api.controllers.families_controller import _hash
from api.repositories import families_repo
from db.connection import session_scope
from schemas.tables import Categories, FamilyInvites, TransactionDB, Users


def _invite(client, headers):
    response = client.post("/families/invites", headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _join(client, headers, code, bring_data=False):
    return client.post("/families/join", json={"code": code, "bring_data": bring_data}, headers=headers)


def _category(db, user, name):
    row = Categories(name=name, family_id=user.family_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def joined(client, user, other_user, auth_headers, headers_for):
    """`other_user` has joined `user`'s family (leaving their own data behind)."""
    assert _join(client, headers_for(other_user), _invite(client, auth_headers)["code"]).status_code == 200


# --- the family and its owner ------------------------------------------------------------------


def test_a_new_person_is_the_owner_of_a_family_with_only_them(client, user, auth_headers):
    data = client.get("/families/me", headers=auth_headers).json()["data"]

    assert data["role"] == "owner"
    assert data["id"] == user.family_id
    assert [(m["id"], m["name"], m["role"]) for m in data["members"]] == [(user.id, "Test User", "owner")]


def test_the_family_page_lists_only_the_callers_family(client, user, other_user, auth_headers):
    members = client.get("/families/me", headers=auth_headers).json()["data"]["members"]

    assert [m["id"] for m in members] == [user.id]  # not other_user, who is in another family


@pytest.mark.parametrize(
    "method, path", [("get", "/families/me"), ("post", "/families/invites"), ("get", "/families/invites")]
)
def test_everything_requires_login(client, method, path):
    assert getattr(client, method)(path).status_code in (401, 403)


# --- creating, listing and cancelling codes ------------------------------------------------------


def test_the_owner_gets_a_long_random_code_once_and_the_database_never_keeps_it(client, db, auth_headers):
    first = _invite(client, auth_headers)
    second = _invite(client, auth_headers)

    assert re.fullmatch(r"([A-Z2-9]{4}-){3}[A-Z2-9]{4}", first["code"])
    assert first["code"] != second["code"]
    stored = db.query(FamilyInvites).filter_by(id=first["id"]).one()
    assert first["code"].replace("-", "") not in (stored.code_hash, stored.code_hint)
    assert stored.code_hint == first["code"][-4:]


def test_a_code_lives_for_about_a_week(client, db, auth_headers):
    created = _invite(client, auth_headers)

    row = db.query(FamilyInvites).filter_by(id=created["id"]).one()
    remaining = row.expires_at - datetime.now()
    assert timedelta(days=6, hours=23) < remaining < timedelta(days=7, hours=1)


def test_the_list_shows_active_codes_without_the_code_itself(client, auth_headers):
    created = _invite(client, auth_headers)

    [item] = client.get("/families/invites", headers=auth_headers).json()["data"]

    assert item["id"] == created["id"] and item["code_hint"] == created["code"][-4:]
    assert "code" not in item and "code_hash" not in item


def test_the_list_leaves_out_used_and_expired_codes(client, db, user, other_user, auth_headers, headers_for):
    used = _invite(client, auth_headers)
    expired = _invite(client, auth_headers)
    active = _invite(client, auth_headers)
    _join(client, headers_for(other_user), used["code"])
    db.query(FamilyInvites).filter_by(id=expired["id"]).update({"expires_at": func.now() - timedelta(minutes=1)})
    db.commit()

    listed = client.get("/families/invites", headers=auth_headers).json()["data"]

    assert [i["id"] for i in listed] == [active["id"]]


def test_a_cancelled_code_no_longer_works(client, user, other_user, auth_headers, headers_for):
    created = _invite(client, auth_headers)

    assert client.delete(f"/families/invites/{created['id']}", headers=auth_headers).status_code == 200

    assert _join(client, headers_for(other_user), created["code"]).status_code == 404
    assert client.get("/families/invites", headers=auth_headers).json()["data"] == []


def test_a_code_of_another_family_cannot_be_cancelled_or_seen(client, user, other_user, auth_headers, headers_for):
    theirs = _invite(client, headers_for(other_user))

    stranger = client.delete(f"/families/invites/{theirs['id']}", headers=auth_headers)
    missing = client.delete("/families/invites/999999", headers=auth_headers)

    assert stranger.status_code == 404 and stranger.json() == missing.json()
    assert client.get("/families/invites", headers=auth_headers).json()["data"] == []
    assert client.get("/families/invites", headers=headers_for(other_user)).json()["data"][0]["id"] == theirs["id"]


def test_a_family_can_have_three_active_codes_and_cancelling_one_frees_a_place(client, auth_headers):
    codes = [_invite(client, auth_headers) for _ in range(3)]

    fourth = client.post("/families/invites", headers=auth_headers)

    assert fourth.status_code == 409
    assert "3 códigos" in fourth.json()["detail"]
    client.delete(f"/families/invites/{codes[0]['id']}", headers=auth_headers)
    assert client.post("/families/invites", headers=auth_headers).status_code == 201


def test_used_and_expired_codes_do_not_count_towards_the_limit(client, db, other_user, auth_headers, headers_for):
    used = _invite(client, auth_headers)
    expired = _invite(client, auth_headers)
    _invite(client, auth_headers)
    _join(client, headers_for(other_user), used["code"])
    db.query(FamilyInvites).filter_by(id=expired["id"]).update({"expires_at": func.now() - timedelta(minutes=1)})
    db.commit()

    assert client.post("/families/invites", headers=auth_headers).status_code == 201


# --- joining ---------------------------------------------------------------------------------------


def test_joining_puts_the_person_in_the_family_as_a_member(client, db, user, other_user, auth_headers, headers_for):
    response = _join(client, headers_for(other_user), _invite(client, auth_headers)["code"])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == user.family_id and data["role"] == "member"
    assert [(m["id"], m["role"]) for m in data["members"]] == [(user.id, "owner"), (other_user.id, "member")]
    db.expire_all()
    assert db.get(Users, other_user.id).family_id == user.family_id


def test_the_code_can_be_typed_in_lower_case_without_dashes(client, user, other_user, auth_headers, headers_for):
    code = _invite(client, auth_headers)["code"]

    response = _join(client, headers_for(other_user), "  " + code.replace("-", "").lower() + " ")

    assert response.status_code == 200


def test_joining_asks_whether_to_bring_the_data(client, user, other_user, auth_headers, headers_for):
    code = _invite(client, auth_headers)["code"]

    response = client.post("/families/join", json={"code": code}, headers=headers_for(other_user))

    assert response.status_code == 422


def test_starting_empty_keeps_the_old_data_behind_and_out_of_sight(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    mine = make_transaction(user, category_ids["Outros"], label="Family's")
    old = make_transaction(other_user, category_ids["Outros"], label="Joiner's old")
    old_category = _category(db, other_user, "Pets da Bia")
    old_family = other_user.family_id

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=False)

    seen = client.post("/transactions/", json={}, headers=headers_for(other_user)).json()["data"]
    assert [t["label"] for t in seen] == ["Family's"]
    categories = {c["name"] for c in client.get("/categories/", headers=headers_for(other_user)).json()["data"]}
    assert "Pets da Bia" not in categories
    db.expire_all()
    assert db.get(TransactionDB, old.id).family_id == old_family  # kept, not deleted
    assert db.get(Categories, old_category.id).family_id == old_family
    assert db.get(TransactionDB, mine.id).family_id == user.family_id


def test_bringing_the_data_moves_the_transactions_and_keeps_who_entered_them(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    make_transaction(user, category_ids["Outros"], label="Family's")
    old = make_transaction(other_user, category_ids["Alimentação"], label="Joiner's old", value=1234)

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    seen = client.post("/transactions/", json={}, headers=auth_headers).json()["data"]  # the owner sees them too
    assert sorted(t["label"] for t in seen) == ["Family's", "Joiner's old"]
    db.expire_all()
    moved = db.get(TransactionDB, old.id)
    assert (moved.family_id, moved.user_id, moved.value) == (user.family_id, other_user.id, 1234)


def test_categories_with_the_same_name_are_merged_ignoring_case_and_accents(
    client, db, user, other_user, auth_headers, headers_for, make_transaction
):
    family_cat = _category(db, user, "Alimentação")
    joiner_cat = _category(db, other_user, "  alimentacao ")
    row = make_transaction(other_user, joiner_cat.id, label="Pizza")
    joiner_cat_id = joiner_cat.id  # the row is about to be deleted

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    db.expire_all()
    assert db.get(TransactionDB, row.id).category_id == family_cat.id  # re-pointed to the family's category
    assert db.query(Categories).filter_by(id=joiner_cat_id).first() is None  # and the duplicate is gone
    names = [c.name for c in db.query(Categories).filter_by(family_id=user.family_id)]
    assert names == ["Alimentação"]


def test_categories_without_a_match_come_along_as_they_are(
    client, db, user, other_user, auth_headers, headers_for, make_transaction
):
    joiner_cat = _category(db, other_user, "Plantas")
    row = make_transaction(other_user, joiner_cat.id, label="Vaso")

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    db.expire_all()
    assert db.get(Categories, joiner_cat.id).family_id == user.family_id
    assert db.get(TransactionDB, row.id).category_id == joiner_cat.id


def test_default_categories_are_never_touched_when_joining(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    make_transaction(other_user, category_ids["Outros"])
    before = db.query(Categories).filter(Categories.family_id.is_(None)).count()

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    assert db.query(Categories).filter(Categories.family_id.is_(None)).count() == before
    assert {c.name for c in db.query(Categories).filter(Categories.family_id.is_(None))} >= {"Outros", "Alimentação"}


def test_joining_is_all_or_nothing(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, monkeypatch
):
    old = make_transaction(other_user, category_ids["Outros"])
    created = _invite(client, auth_headers)
    old_family = other_user.family_id

    def move_then_fail(db, old_family_id, new_family_id):
        db.query(TransactionDB).filter_by(family_id=old_family_id).update({"family_id": new_family_id})
        raise RuntimeError("boom")

    monkeypatch.setattr(families_repo, "_bring_data", move_then_fail)
    with session_scope() as attempt, pytest.raises(RuntimeError):  # a session of its own, like a request has
        families_repo.join_family(attempt, attempt.get(Users, other_user.id), _hash(created["code"]), True)

    db.expire_all()
    assert db.get(Users, other_user.id).family_id == old_family
    assert db.get(Users, other_user.id).role == "owner"
    assert db.get(TransactionDB, old.id).family_id == old_family
    assert db.get(FamilyInvites, created["id"]).used_at is None  # the code was not used up


# --- the rules ---------------------------------------------------------------------------------------


def test_a_code_works_only_once(client, make_user, user, other_user, auth_headers, headers_for):
    code = _invite(client, auth_headers)["code"]
    third = make_user("Third")

    assert _join(client, headers_for(other_user), code).status_code == 200
    again = _join(client, headers_for(third), code)

    assert again.status_code == 404
    assert [m["id"] for m in client.get("/families/me", headers=auth_headers).json()["data"]["members"]] == [
        user.id,
        other_user.id,
    ]


def test_an_expired_code_does_not_work(client, db, user, other_user, auth_headers, headers_for):
    created = _invite(client, auth_headers)
    db.query(FamilyInvites).filter_by(id=created["id"]).update({"expires_at": func.now() - timedelta(seconds=1)})
    db.commit()

    response = _join(client, headers_for(other_user), created["code"])

    assert response.status_code == 404
    assert db.get(Users, other_user.id).family_id != user.family_id


def test_wrong_used_and_expired_codes_all_get_the_same_answer(
    client, db, make_user, user, other_user, auth_headers, headers_for
):
    used = _invite(client, auth_headers)["code"]
    _join(client, headers_for(other_user), used)
    expired = _invite(client, auth_headers)
    db.query(FamilyInvites).filter_by(id=expired["id"]).update({"expires_at": func.now() - timedelta(days=1)})
    db.commit()
    stranger = headers_for(make_user("Stranger"))

    answers = [_join(client, stranger, code) for code in (used, expired["code"], "AAAA-BBBB-CCCC-DDDD", "")]

    assert {a.status_code for a in answers} == {404}
    assert len({a.text for a in answers}) == 1  # nothing says which codes exist


def test_someone_in_a_family_with_other_people_cannot_join_another_family(
    client, db, make_user, user, other_user, auth_headers, headers_for, joined
):
    elsewhere = make_user("Owner elsewhere")
    code = _invite(client, headers_for(elsewhere))

    response = _join(client, headers_for(other_user), code["code"])  # other_user shares a family with user

    assert response.status_code == 409
    assert "outras pessoas" in response.json()["detail"]
    assert db.get(Users, other_user.id).family_id == user.family_id
    assert db.get(FamilyInvites, code["id"]).used_at is None  # the code was not wasted


def test_the_owner_of_a_shared_family_cannot_walk_out_of_it_by_joining_another(
    client, db, make_user, user, auth_headers, headers_for, joined
):
    code = _invite(client, headers_for(make_user("Elsewhere")))

    response = _join(client, auth_headers, code["code"])

    assert response.status_code == 409  # the family would be left without its owner
    assert db.get(Users, user.id).role == "owner"


def test_a_code_for_the_family_you_are_already_in_is_refused_and_not_used_up(client, db, user, auth_headers):
    created = _invite(client, auth_headers)

    response = _join(client, auth_headers, created["code"])

    assert response.status_code == 409
    assert db.get(FamilyInvites, created["id"]).used_at is None


def test_members_cannot_invite_list_or_cancel(client, user, other_user, auth_headers, headers_for, joined):
    owners_code = _invite(client, auth_headers)
    member = headers_for(other_user)

    assert client.post("/families/invites", headers=member).status_code == 403
    assert client.get("/families/invites", headers=member).status_code == 403
    assert client.delete(f"/families/invites/{owners_code['id']}", headers=member).status_code == 403
    assert client.get("/families/invites", headers=auth_headers).json()["data"][0]["id"] == owners_code["id"]


def test_the_codes_of_a_family_someone_left_stop_working(
    client, db, make_user, user, other_user, auth_headers, headers_for
):
    """The joiner's old family is empty but still holds their old data: its codes must not open it to a stranger."""
    old_code = _invite(client, headers_for(other_user))
    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"])
    stranger = headers_for(make_user("Stranger"))

    assert _join(client, stranger, old_code["code"]).status_code == 404
    assert db.query(FamilyInvites).filter_by(id=old_code["id"]).count() == 0


def test_the_joiner_shares_the_budget_afterwards(
    client, user, other_user, auth_headers, headers_for, make_transaction, category_ids, joined
):
    make_transaction(user, category_ids["Outros"], label="Owner's")
    created = client.post(
        "/transactions/create",
        json={"label": "Joiner's", "value": 100, "category_id": category_ids["Outros"]},
        headers=headers_for(other_user),
    )
    assert created.status_code == 201

    seen = client.post("/transactions/", json={}, headers=auth_headers).json()["data"]

    assert sorted(t["label"] for t in seen) == ["Joiner's", "Owner's"]


def test_several_categories_that_fold_to_the_same_name_all_merge_into_one(
    client, db, user, other_user, auth_headers, headers_for, make_transaction
):
    family_cat = _category(db, user, "Alimentação")
    first, second = _category(db, other_user, "alimentacao"), _category(db, other_user, "ALIMENTAÇÃO ")
    a = make_transaction(other_user, first.id, label="A")
    b = make_transaction(other_user, second.id, label="B")

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    db.expire_all()
    assert {db.get(TransactionDB, a.id).category_id, db.get(TransactionDB, b.id).category_id} == {family_cat.id}
    assert [c.name for c in db.query(Categories).filter_by(family_id=user.family_id)] == ["Alimentação"]


def test_two_of_the_joiners_own_categories_with_the_same_name_become_one_when_the_family_has_none(
    client, db, user, other_user, auth_headers, headers_for, make_transaction
):
    first, second = _category(db, other_user, "Plantas"), _category(db, other_user, "plantas")
    a = make_transaction(other_user, first.id, label="A")
    b = make_transaction(other_user, second.id, label="B")

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    db.expire_all()
    names = [c.name for c in db.query(Categories).filter_by(family_id=user.family_id)]
    assert names == ["Plantas"]  # the first one kept, the second merged into it
    assert db.get(TransactionDB, a.id).category_id == db.get(TransactionDB, b.id).category_id


def test_a_failure_after_the_data_has_been_moved_undoes_all_of_it(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, monkeypatch
):
    """The real merge runs; only the final commit fails. Nothing may stay half done."""
    family_cat = _category(db, user, "Alimentação")
    joiner_cat = _category(db, other_user, "alimentacao")
    row = make_transaction(other_user, joiner_cat.id)
    created = _invite(client, auth_headers)
    old_family, joiner_cat_id = other_user.family_id, joiner_cat.id

    with session_scope() as attempt, pytest.raises(RuntimeError):
        monkeypatch.setattr(attempt, "commit", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        families_repo.join_family(attempt, attempt.get(Users, other_user.id), _hash(created["code"]), True)

    db.expire_all()
    assert db.get(Users, other_user.id).family_id == old_family
    assert db.get(TransactionDB, row.id).family_id == old_family
    assert db.get(TransactionDB, row.id).category_id == joiner_cat_id  # not re-pointed
    assert db.query(Categories).filter_by(id=joiner_cat_id).first() is not None  # not deleted
    assert db.get(FamilyInvites, created["id"]).used_at is None
    assert family_cat.id != joiner_cat_id


def test_a_category_with_an_emoji_is_merged_with_the_same_words_without_one(
    client, db, user, other_user, auth_headers, headers_for, make_transaction
):
    family_cat = _category(db, user, "Plantas")
    joiner_cat = _category(db, other_user, "🌱 plantas")
    row = make_transaction(other_user, joiner_cat.id, label="Vaso")
    joiner_cat_id = joiner_cat.id

    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring_data=True)

    db.expire_all()
    assert db.get(TransactionDB, row.id).category_id == family_cat.id
    assert db.query(Categories).filter_by(id=joiner_cat_id).first() is None
    assert [c.name for c in db.query(Categories).filter_by(family_id=user.family_id)] == ["Plantas"]

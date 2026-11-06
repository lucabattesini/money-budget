"""Leaving a family behind when joining another one: kept for 30 days, then deleted (TKT-43).

`user` is alone in their own family and invites `other_user`, who also starts alone with data of their own.
Times are shifted with the database clock, the same one the code uses.
"""

from datetime import datetime, timedelta

from sqlalchemy import func

from api.controllers.families_controller import _hash
from schemas.tables import Categories, ExportJobDB, Families, FamilyInvites, TransactionDB, Users


def _invite(client, headers):
    response = client.post("/families/invites", headers=headers)
    assert response.status_code == 201
    return response.json()["data"]


def _join(client, headers, code, bring_data):
    return client.post("/families/join", json={"code": code, "bring_data": bring_data}, headers=headers)


def _back(client, headers):
    return client.post("/families/rollback", headers=headers)


def _me(client, headers):
    return client.get("/families/me", headers=headers).json()["data"]


def _days_ago(db, family_id, days):
    db.query(Families).filter_by(id=family_id).update({"abandoned_at": func.now() - timedelta(days=days)})
    db.commit()


def _exists(db, model, id):
    return db.query(model).filter_by(id=id).first() is not None


def _joiner_with_data(client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring):
    """other_user has a transaction and a category of their own, then joins user's family."""
    make_transaction(other_user, category_ids["Sem categoria"], label="Joiner's old")
    category = Categories(name="Plantas", family_id=other_user.family_id)
    db.add(category)
    db.commit()
    response = _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], bring)
    assert response.status_code == 200
    db.expire_all()


# --- the old family is marked and remembered -----------------------------------------------------------


def test_the_family_left_behind_is_marked_abandoned_and_the_ones_still_in_use_are_not(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old = other_user.family_id
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )

    assert db.get(Families, old).abandoned_at is not None
    assert db.get(Families, user.family_id).abandoned_at is None


def test_starting_empty_remembers_where_to_go_back_to_and_bringing_the_data_does_not(
    client, db, make_user, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    empty_old, brought_old = other_user.family_id, make_user("Brought").family_id
    third = db.query(Users).filter_by(family_id=brought_old).one()
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    assert _join(client, headers_for(third), _invite(client, auth_headers)["code"], True).status_code == 200
    db.expire_all()

    assert db.get(Users, other_user.id).previous_family_id == empty_old
    assert db.get(Users, third.id).previous_family_id is None


def test_the_family_page_says_until_when_the_person_can_go_back(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    assert _me(client, headers_for(other_user))["previous_family"] is None  # never joined anything
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )

    until = datetime.fromisoformat(_me(client, headers_for(other_user))["previous_family"]["available_until"])

    assert timedelta(days=29, hours=23) < until - datetime.now() < timedelta(days=30, hours=1)
    assert _me(client, auth_headers)["previous_family"] is None  # the owner left nothing behind


def test_nothing_to_go_back_to_when_the_data_was_brought_along(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=True
    )

    assert _me(client, headers_for(other_user))["previous_family"] is None
    assert _back(client, headers_for(other_user)).status_code == 404


# --- going back --------------------------------------------------------------------------------------


def test_going_back_returns_the_person_to_their_old_data_as_its_owner(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old = other_user.family_id
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    mine = headers_for(other_user)
    assert [t["label"] for t in client.post("/transactions/", json={}, headers=mine).json()["data"]] == []

    response = _back(client, mine)

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["id"], data["role"], data["previous_family"]) == (str(old), "owner", None)
    assert [t["label"] for t in client.post("/transactions/", json={}, headers=mine).json()["data"]] == ["Joiner's old"]
    assert "Plantas" in {c["name"] for c in client.get("/categories/", headers=mine).json()["data"]}
    db.expire_all()
    assert db.get(Families, old).abandoned_at is None  # in use again, so it is no longer on its way out


def test_what_was_entered_in_the_new_family_stays_in_it(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    client.post(
        "/transactions/create",
        json={"label": "Entered while in the family", "value": 100, "category_id": category_ids["Sem categoria"]},
        headers=headers_for(other_user),
    )

    _back(client, headers_for(other_user))

    seen_by_owner = [t["label"] for t in client.post("/transactions/", json={}, headers=auth_headers).json()["data"]]
    seen_by_joiner = [
        t["label"] for t in client.post("/transactions/", json={}, headers=headers_for(other_user)).json()["data"]
    ]
    assert seen_by_owner == ["Entered while in the family"]
    assert seen_by_joiner == ["Joiner's old"]
    assert [m["id"] for m in _me(client, auth_headers)["members"]] == [
        str(user.id)
    ]  # the family they left has no trace of them


def test_a_person_can_only_go_back_once(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    assert _back(client, headers_for(other_user)).status_code == 200

    assert _back(client, headers_for(other_user)).status_code == 404


def test_the_family_just_left_is_kept_for_30_days_too_when_nobody_is_left_in_it(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    """A family can lose its last person by someone going back, so it follows the same 30-day rule."""
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    emptied_id = user.family_id
    code = _invite(client, auth_headers)  # an unused code of the family about to be emptied
    elsewhere = Families()
    db.add(elsewhere)
    db.flush()
    db.query(Users).filter_by(id=user.id).update(
        {"family_id": elsewhere.id}
    )  # the owner is gone: only the joiner is left
    db.commit()

    assert _back(client, headers_for(other_user)).status_code == 200

    db.expire_all()
    assert db.get(Families, emptied_id).abandoned_at is not None  # nobody is in it: its 30 days start now
    assert db.query(FamilyInvites).filter_by(id=code["id"]).count() == 0  # and its codes stop working


def test_an_owner_of_a_family_with_other_people_cannot_walk_out_of_it(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )
    db.query(Users).filter_by(id=other_user.id).update({"role": "owner"})
    db.commit()

    response = _back(client, headers_for(other_user))

    assert response.status_code == 409
    assert db.get(Users, other_user.id).family_id == user.family_id


def test_the_last_day_still_counts_and_the_day_after_does_not(
    client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old = other_user.family_id
    _joiner_with_data(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids, bring=False
    )

    _days_ago(db, old, 31)
    too_late = _back(client, headers_for(other_user))
    _days_ago(db, old, 29)
    in_time = _back(client, headers_for(other_user))

    assert (too_late.status_code, in_time.status_code) == (404, 200)


# --- deleting what nobody came back for ------------------------------------------------------------------


def _abandoned_family_with_everything(client, db, user, other_user, auth_headers, headers_for, make_transaction, ids):
    old = other_user.family_id
    row = make_transaction(other_user, ids["Sem categoria"], label="Joiner's old")
    category = Categories(name="Plantas", family_id=old)
    job = ExportJobDB(family_id=old, requested_by=other_user.id, format="csv", status="done", content=b"x")
    db.add_all([category, job])
    db.commit()
    kept = (row.id, category.id, job.id)
    _join(client, headers_for(other_user), _invite(client, auth_headers)["code"], False)
    db.expire_all()
    return old, kept


def test_a_family_nobody_came_back_to_is_deleted_with_everything_it_holds_when_someone_joins(
    client, db, make_user, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old, (transaction_id, category_id, job_id) = _abandoned_family_with_everything(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
    )
    _days_ago(db, old, 31)

    assert (
        _join(client, headers_for(make_user("Newcomer")), _invite(client, auth_headers)["code"], False).status_code
        == 200
    )

    db.expire_all()
    assert not _exists(db, Families, old)
    assert not _exists(db, TransactionDB, transaction_id)
    assert not _exists(db, Categories, category_id)
    assert not _exists(db, ExportJobDB, job_id)
    assert db.get(Users, other_user.id).previous_family_id is None  # nothing left to go back to
    assert _me(client, headers_for(other_user))["previous_family"] is None
    assert _exists(db, Users, other_user.id)  # the person is untouched: only the abandoned family went


def test_a_family_abandoned_less_than_30_days_ago_is_kept_when_someone_joins(
    client, db, make_user, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old, (transaction_id, category_id, _) = _abandoned_family_with_everything(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
    )
    _days_ago(db, old, 29)

    _join(client, headers_for(make_user("Newcomer")), _invite(client, auth_headers)["code"], False)

    db.expire_all()
    assert _exists(db, Families, old) and _exists(db, TransactionDB, transaction_id)
    assert _exists(db, Categories, category_id)


def test_a_family_with_people_in_it_is_never_deleted_whatever_its_date_says(
    client, db, make_user, user, other_user, auth_headers, headers_for
):
    db.query(Families).filter_by(id=user.family_id).update({"abandoned_at": func.now() - timedelta(days=90)})
    db.commit()

    _join(client, headers_for(make_user("Newcomer")), _invite(client, auth_headers)["code"], False)

    db.expire_all()
    assert _exists(db, Families, user.family_id) and _exists(db, Users, user.id)


def test_deleting_a_family_leaves_no_one_elses_transaction_pointing_at_its_categories(
    client, db, make_user, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    old, (_, category_id, _) = _abandoned_family_with_everything(
        client, db, user, other_user, auth_headers, headers_for, make_transaction, category_ids
    )
    stray = make_transaction(user, category_id)  # cannot happen through the API; the purge must not break on it
    _days_ago(db, old, 31)

    assert (
        _join(client, headers_for(make_user("Newcomer")), _invite(client, auth_headers)["code"], False).status_code
        == 200
    )

    db.expire_all()
    assert db.get(TransactionDB, stray.id).category_id is None


# --- a family nobody is in cannot be joined ----------------------------------------------------------------


def test_a_code_of_a_family_with_nobody_in_it_does_not_work_and_is_not_used_up(
    client, db, user, other_user, auth_headers, headers_for
):
    empty = Families()
    db.add(empty)
    db.flush()
    stale = FamilyInvites(
        family_id=empty.id,
        created_by=user.id,
        code_hash=_hash("EMPTY-FAMILY-CODE"),
        code_hint="0000",
        expires_at=func.now() + timedelta(days=1),
    )
    db.add(stale)
    db.commit()

    response = _join(client, headers_for(other_user), "EMPTY-FAMILY-CODE", False)

    assert response.status_code == 404
    db.expire_all()
    assert db.get(FamilyInvites, stale.id).used_at is None
    assert db.get(Users, other_user.id).family_id != empty.id

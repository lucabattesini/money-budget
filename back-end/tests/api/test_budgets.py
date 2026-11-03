"""Monthly budgets per category (TKT-61): what a family plans to spend and how it is going."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func

from api.repositories import families_repo
from schemas.tables import Budgets, Categories, CategoryGroups, Families, Users

NOV = "2026-11"


def _month(client, headers, month=NOV):
    response = client.get("/budgets", params={"month": month}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _plan(client, headers, category_id, amount, month=NOV):
    return client.put("/budgets", json={"category_id": category_id, "month": month, "amount": amount}, headers=headers)


def _row(data, category_id):
    for group in data["groups"]:
        for category in group["categories"]:
            if category["id"] == category_id:
                return category
    raise AssertionError(f"category {category_id} is not on the page")


def _default_in(db, group_name, name):
    group = db.query(CategoryGroups).filter_by(name=group_name).one()
    row = Categories(name=name, group_id=group.id)
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def food(category_ids):
    return category_ids["Restaurantes e Bares"]


# --- what the page shows -------------------------------------------------------------------------------


def test_an_empty_month_lists_the_spending_categories_under_their_groups_with_nothing_planned(
    client, auth_headers, food
):
    data = _month(client, auth_headers)

    assert data["month"] == NOV
    assert data["totals"] == {"budgeted": 0, "spent": 0, "unbudgeted_spent": 0, "remaining": 0}
    assert "Restaurantes e Bares" in [c["name"] for g in data["groups"] for c in g["categories"]]
    assert _row(data, food) == {"id": food, "name": "Restaurantes e Bares", "budgeted": None, "spent": 0}
    assert [g["name"] for g in data["groups"] if g["name"] == "Alimentação"] == ["Alimentação"]


def test_income_and_transfer_categories_are_not_offered_a_budget(client, db, auth_headers):
    salary = _default_in(db, "Receitas", "💰 Salário")
    transfer = _default_in(db, "Transferências", "🔄 Transferência")

    data = _month(client, auth_headers)

    ids = {c["id"] for g in data["groups"] for c in g["categories"]}
    assert salary.id not in ids and transfer.id not in ids
    assert {g["name"] for g in data["groups"]}.isdisjoint({"Receitas", "Transferências"})


def test_the_groups_come_in_the_order_they_are_shown_everywhere(client, db, auth_headers):
    data = _month(client, auth_headers)

    order = [g.name for g in db.query(CategoryGroups).order_by(CategoryGroups.id)]
    shown = [g["name"] for g in data["groups"]]
    assert shown == [name for name in order if name in shown]


def test_categories_inside_a_group_are_sorted_by_their_words_not_their_emoji(client, db, auth_headers, user):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    db.add_all(
        [
            Categories(name="🅱️ Zebra", group_id=group.id, family_id=user.family_id),
            Categories(name="🅰️ Abelha", group_id=group.id, family_id=user.family_id),
        ]
    )
    db.commit()

    names = [
        c["name"] for g in _month(client, auth_headers)["groups"] if g["name"] == "Outros" for c in g["categories"]
    ]

    assert names.index("🅰️ Abelha") < names.index("🅱️ Zebra")


def test_a_family_sees_its_own_categories_and_never_anothers(client, db, auth_headers, user, other_user, headers_for):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    mine = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    theirs = Categories(name="Cavalos", group_id=group.id, family_id=other_user.family_id)
    db.add_all([mine, theirs])
    db.commit()

    names = {c["name"] for g in _month(client, auth_headers)["groups"] for c in g["categories"]}
    others = {c["name"] for g in _month(client, headers_for(other_user))["groups"] for c in g["categories"]}

    assert "Plantas" in names and "Cavalos" not in names
    assert "Cavalos" in others and "Plantas" not in others


# --- planning --------------------------------------------------------------------------------------------


def test_a_planned_amount_is_saved_for_that_month_only_and_the_answer_shows_the_month(client, auth_headers, food):
    response = _plan(client, auth_headers, food, 50000)

    assert response.status_code == 200
    assert _row(response.json()["data"], food)["budgeted"] == 50000
    assert response.json()["data"]["totals"]["budgeted"] == 50000
    assert _row(_month(client, auth_headers), food)["budgeted"] == 50000
    assert _row(_month(client, auth_headers, "2026-12"), food)["budgeted"] is None
    assert _row(_month(client, auth_headers, "2026-10"), food)["budgeted"] is None


def test_planning_again_changes_the_amount_and_keeps_one_row(client, db, auth_headers, food):
    _plan(client, auth_headers, food, 50000)
    _plan(client, auth_headers, food, 70000)

    assert _row(_month(client, auth_headers), food)["budgeted"] == 70000
    assert db.query(Budgets).count() == 1


def test_zero_removes_the_budget(client, db, auth_headers, food):
    _plan(client, auth_headers, food, 50000)

    response = _plan(client, auth_headers, food, 0)

    assert response.status_code == 200
    assert _row(response.json()["data"], food)["budgeted"] is None
    assert db.query(Budgets).count() == 0


def test_removing_a_budget_that_was_never_set_is_fine(client, auth_headers, food):
    assert _plan(client, auth_headers, food, 0).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"month": "2026-13", "amount": 100},
        {"month": "2026-00", "amount": 100},
        {"month": "2026-1", "amount": 100},
        {"month": "novembro", "amount": 100},
        {"month": "2026-11-01", "amount": 100},
        {"month": "0000-01", "amount": 100},  # not a date Python can write
        {"month": "9999-12", "amount": 100},  # its next month does not exist
        {"month": "1999-12", "amount": 100},
        {"month": "2100-01", "amount": 100},
        {"month": NOV, "amount": -1},
        {"month": NOV, "amount": 2147483648},  # does not fit the database column
        {"month": NOV, "amount": 12.5},
        {"month": NOV},
        {"amount": 100},
    ],
)
def test_a_bad_request_is_refused_and_nothing_is_saved(client, db, auth_headers, food, body):
    response = client.put("/budgets", json={"category_id": food, **body}, headers=auth_headers)

    assert response.status_code == 422
    assert db.query(Budgets).count() == 0


def test_the_biggest_amount_that_fits_is_accepted(client, auth_headers, food):
    assert _plan(client, auth_headers, food, 2147483647).status_code == 200


def test_a_category_that_is_not_the_familys_or_has_no_budget_answers_404(
    client, db, auth_headers, other_user, food, headers_for
):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    theirs = Categories(name="Cavalos", group_id=group.id, family_id=other_user.family_id)
    salary = _default_in(db, "Receitas", "💰 Salário")
    db.add(theirs)
    db.commit()

    for category_id in (theirs.id, salary.id, 999999):
        assert _plan(client, auth_headers, category_id, 100).status_code == 404
    assert db.query(Budgets).count() == 0


def test_budgets_need_login(client, food):
    assert client.get("/budgets", params={"month": NOV}).status_code in (401, 403)
    assert client.put("/budgets", json={"category_id": food, "month": NOV, "amount": 1}).status_code in (401, 403)
    assert client.post("/budgets/copy", json={"from_month": NOV, "to_month": "2026-12"}).status_code in (401, 403)


def test_the_month_is_required_and_must_look_like_a_month(client, auth_headers):
    assert client.get("/budgets", headers=auth_headers).status_code == 422
    assert client.get("/budgets", params={"month": "2026-13"}, headers=auth_headers).status_code == 422


def test_the_list_is_served_at_both_addresses_without_a_redirect(client, auth_headers):
    assert (
        client.get("/budgets/", params={"month": NOV}, headers=auth_headers, follow_redirects=False).status_code == 200
    )


# --- how it is going -----------------------------------------------------------------------------------


def test_spent_counts_only_money_going_out_in_that_month(client, auth_headers, user, food, make_transaction):
    make_transaction(user, food, value=3000, when=datetime(2026, 11, 5, 12))
    make_transaction(user, food, value=2000, when=datetime(2026, 11, 20, 12))
    make_transaction(user, food, value=9999, when=datetime(2026, 11, 6, 12), type="credit")  # money coming in
    make_transaction(user, food, value=7000, when=datetime(2026, 10, 31, 23, 59, 59))  # last month, one second early
    make_transaction(user, food, value=8000, when=datetime(2026, 12, 1, 0, 0, 0))  # next month, the first moment

    assert _row(_month(client, auth_headers), food)["spent"] == 5000
    assert _row(_month(client, auth_headers, "2026-12"), food)["spent"] == 8000


def test_december_runs_into_january_without_a_gap(client, auth_headers, user, food, make_transaction):
    make_transaction(user, food, value=100, when=datetime(2026, 12, 31, 23, 59, 59))
    make_transaction(user, food, value=200, when=datetime(2027, 1, 1, 0, 0, 0))

    assert _row(_month(client, auth_headers, "2026-12"), food)["spent"] == 100
    assert _row(_month(client, auth_headers, "2027-01"), food)["spent"] == 200


def test_totals_compare_what_was_planned_with_what_was_spent_in_those_categories(
    client, auth_headers, user, category_ids, make_transaction
):
    food, rent, transport = (category_ids[n] for n in ("Restaurantes e Bares", "Aluguel", "Transporte público"))
    _plan(client, auth_headers, food, 50000)
    _plan(client, auth_headers, rent, 180000)
    make_transaction(user, food, value=20000, when=datetime(2026, 11, 3, 12))
    make_transaction(user, rent, value=180000, when=datetime(2026, 11, 5, 12))
    make_transaction(user, transport, value=4500, when=datetime(2026, 11, 7, 12))  # no budget

    data = _month(client, auth_headers)

    assert data["totals"] == {"budgeted": 230000, "spent": 200000, "unbudgeted_spent": 4500, "remaining": 30000}
    by_group = {g["name"]: g for g in data["groups"]}
    assert (by_group["Alimentação"]["budgeted"], by_group["Alimentação"]["spent"]) == (50000, 20000)
    assert (by_group["Moradia"]["budgeted"], by_group["Moradia"]["spent"]) == (180000, 180000)
    assert (by_group["Auto e Transporte"]["budgeted"], by_group["Auto e Transporte"]["spent"]) == (0, 0)
    assert _row(data, transport) == {"id": transport, "name": "Transporte público", "budgeted": None, "spent": 4500}


def test_going_over_the_plan_makes_what_is_left_negative(client, auth_headers, user, food, make_transaction):
    _plan(client, auth_headers, food, 10000)
    make_transaction(user, food, value=15000, when=datetime(2026, 11, 3, 12))

    assert _month(client, auth_headers)["totals"]["remaining"] == -5000


def test_spending_in_income_or_transfer_categories_is_not_counted_as_spending(
    client, db, auth_headers, user, make_transaction
):
    transfer = _default_in(db, "Transferências", "🔄 Transferência")
    make_transaction(user, transfer.id, value=50000, when=datetime(2026, 11, 3, 12))  # paying a card bill, say

    assert _month(client, auth_headers)["totals"]["unbudgeted_spent"] == 0


def test_a_family_never_sees_another_familys_plan_or_spending(
    client, auth_headers, user, other_user, headers_for, food, make_transaction
):
    _plan(client, auth_headers, food, 50000)
    make_transaction(user, food, value=1000, when=datetime(2026, 11, 3, 12))
    make_transaction(other_user, food, value=99900, when=datetime(2026, 11, 3, 12))

    theirs = _month(client, headers_for(other_user))

    assert _row(theirs, food)["budgeted"] is None
    assert _row(theirs, food)["spent"] == 99900
    assert theirs["totals"]["budgeted"] == 0
    assert _row(_month(client, auth_headers), food)["spent"] == 1000


def test_two_families_can_plan_the_same_category_for_the_same_month(
    client, db, auth_headers, other_user, headers_for, food
):
    _plan(client, auth_headers, food, 50000)
    _plan(client, headers_for(other_user), food, 70000)

    assert _row(_month(client, auth_headers), food)["budgeted"] == 50000
    assert _row(_month(client, headers_for(other_user)), food)["budgeted"] == 70000
    assert db.query(Budgets).count() == 2


# --- copying a month -------------------------------------------------------------------------------------


def _copy(client, headers, source=NOV, target="2026-12"):
    return client.post("/budgets/copy", json={"from_month": source, "to_month": target}, headers=headers)


def test_copying_fills_the_month_with_last_months_amounts(client, auth_headers, category_ids):
    food, rent = category_ids["Restaurantes e Bares"], category_ids["Aluguel"]
    _plan(client, auth_headers, food, 50000)
    _plan(client, auth_headers, rent, 180000)

    response = _copy(client, auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["copied"] == 2
    assert response.json()["data"]["month"] == "2026-12"
    december = _month(client, auth_headers, "2026-12")
    assert (_row(december, food)["budgeted"], _row(december, rent)["budgeted"]) == (50000, 180000)
    assert _row(_month(client, auth_headers), food)["budgeted"] == 50000  # the source is untouched


def test_copying_never_overwrites_what_is_already_planned(client, auth_headers, category_ids):
    food, rent = category_ids["Restaurantes e Bares"], category_ids["Aluguel"]
    _plan(client, auth_headers, food, 50000)
    _plan(client, auth_headers, rent, 180000)
    _plan(client, auth_headers, food, 12300, month="2026-12")

    response = _copy(client, auth_headers)

    assert response.json()["data"]["copied"] == 1
    december = _month(client, auth_headers, "2026-12")
    assert (_row(december, food)["budgeted"], _row(december, rent)["budgeted"]) == (12300, 180000)


def test_copying_an_empty_month_copies_nothing(client, auth_headers):
    response = _copy(client, auth_headers, source="2026-09")

    assert response.status_code == 200
    assert response.json()["data"]["copied"] == 0


def test_copying_a_month_onto_itself_is_refused(client, auth_headers):
    assert _copy(client, auth_headers, source=NOV, target=NOV).status_code == 422


def test_copying_with_a_bad_month_is_refused(client, auth_headers):
    assert _copy(client, auth_headers, source="2026-13").status_code == 422


def test_copying_only_touches_the_callers_own_family(client, auth_headers, other_user, headers_for, food):
    _plan(client, headers_for(other_user), food, 70000)

    assert _copy(client, auth_headers).json()["data"]["copied"] == 0
    assert _row(_month(client, headers_for(other_user), "2026-12"), food)["budgeted"] is None


# --- when categories and families change ---------------------------------------------------------------


def test_deleting_a_category_deletes_its_budgets(client, db, auth_headers, user):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    plants = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    db.add(plants)
    db.commit()
    _plan(client, auth_headers, plants.id, 5000)
    _plan(client, auth_headers, plants.id, 6000, month="2026-12")

    assert client.delete(f"/categories/{plants.id}", headers=auth_headers).status_code in (200, 204)

    assert db.query(Budgets).count() == 0


def test_a_category_in_use_is_refused_and_keeps_its_budgets(client, db, auth_headers, user, make_transaction):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    plants = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    db.add(plants)
    db.commit()
    make_transaction(user, plants.id)
    _plan(client, auth_headers, plants.id, 5000)

    assert client.delete(f"/categories/{plants.id}", headers=auth_headers).status_code == 409

    assert db.query(Budgets).count() == 1


def _family_of(row):
    class _Family:
        id = row.family_id

    return _Family


def test_joining_with_the_data_brings_the_budgets_along(db, user, other_user, category_ids):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    own = Categories(name="Plantas", group_id=group.id, family_id=other_user.family_id)
    db.add(own)
    db.commit()
    food = category_ids["Restaurantes e Bares"]
    db.add_all(
        [
            Budgets(family_id=other_user.family_id, category_id=own.id, month=date(2026, 11, 1), amount=500),
            Budgets(family_id=other_user.family_id, category_id=food, month=date(2026, 11, 1), amount=700),
        ]
    )
    db.commit()

    families_repo._bring_data(db, other_user.family_id, user.family_id)
    db.commit()

    rows = {(b.family_id, b.category_id): b.amount for b in db.query(Budgets)}
    assert rows == {(user.family_id, own.id): 500, (user.family_id, food): 700}


def test_when_both_families_planned_the_same_category_the_new_familys_plan_wins(db, user, other_user, category_ids):
    food = category_ids["Restaurantes e Bares"]
    db.add_all(
        [
            Budgets(family_id=user.family_id, category_id=food, month=date(2026, 11, 1), amount=100),
            Budgets(family_id=other_user.family_id, category_id=food, month=date(2026, 11, 1), amount=900),
            Budgets(family_id=other_user.family_id, category_id=food, month=date(2026, 12, 1), amount=800),
        ]
    )
    db.commit()

    families_repo._bring_data(db, other_user.family_id, user.family_id)
    db.commit()

    rows = {(b.month, b.amount) for b in db.query(Budgets) if b.family_id == user.family_id}
    assert rows == {(date(2026, 11, 1), 100), (date(2026, 12, 1), 800)}
    assert db.query(Budgets).filter_by(family_id=other_user.family_id).count() == 0


def test_a_category_merged_into_one_with_the_same_name_hands_its_budgets_to_it(db, user, other_user):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    mine = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    theirs = Categories(name="🌱 plantas", group_id=group.id, family_id=other_user.family_id)
    db.add_all([mine, theirs])
    db.commit()
    db.add_all(
        [
            Budgets(family_id=other_user.family_id, category_id=theirs.id, month=date(2026, 11, 1), amount=300),
            Budgets(family_id=other_user.family_id, category_id=theirs.id, month=date(2026, 12, 1), amount=400),
            Budgets(family_id=user.family_id, category_id=mine.id, month=date(2026, 12, 1), amount=999),
        ]
    )
    db.commit()
    gone = theirs.id

    families_repo._bring_data(db, other_user.family_id, user.family_id)
    db.commit()

    rows = {(b.category_id, b.month, b.amount) for b in db.query(Budgets)}
    assert rows == {(mine.id, date(2026, 11, 1), 300), (mine.id, date(2026, 12, 1), 999)}
    assert db.get(Categories, gone) is None


def test_deleting_an_abandoned_family_deletes_its_budgets_and_no_one_elses(db, user, other_user, category_ids):
    food = category_ids["Restaurantes e Bares"]
    db.add_all(
        [
            Budgets(family_id=other_user.family_id, category_id=food, month=date(2026, 11, 1), amount=100),
            Budgets(family_id=user.family_id, category_id=food, month=date(2026, 11, 1), amount=200),
        ]
    )
    db.query(Users).filter_by(id=other_user.id).delete()
    db.query(Families).filter_by(id=other_user.family_id).update({"abandoned_at": func.now() - timedelta(days=31)})
    db.commit()

    families_repo.purge_abandoned_families(db)

    assert [(b.family_id, b.amount) for b in db.query(Budgets)] == [(user.family_id, 200)]


@pytest.mark.parametrize("month", ["0000-01", "9999-12", "2100-01", "1999-12"])
def test_a_month_outside_the_years_offered_is_refused_everywhere_not_a_server_error(client, auth_headers, month):
    assert client.get("/budgets", params={"month": month}, headers=auth_headers).status_code == 422
    assert _copy(client, auth_headers, source=month, target=NOV).status_code == 422
    assert _copy(client, auth_headers, source=NOV, target=month).status_code == 422


def test_the_first_and_last_months_offered_work(client, auth_headers):
    assert _month(client, auth_headers, "2000-01")["month"] == "2000-01"
    assert _month(client, auth_headers, "2099-12")["month"] == "2099-12"


def test_a_category_moved_to_an_income_group_loses_its_budgets(client, db, auth_headers, user):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    income = db.query(CategoryGroups).filter_by(name="Receitas").one()
    plants = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    db.add(plants)
    db.commit()
    _plan(client, auth_headers, plants.id, 5000)

    assert (
        client.patch(f"/categories/{plants.id}", json={"group_id": income.id}, headers=auth_headers).status_code == 200
    )

    assert db.query(Budgets).count() == 0  # nothing hidden is kept, so nothing can be copied later


def test_a_category_moved_to_another_spending_group_keeps_its_budgets(client, db, auth_headers, user):
    group = db.query(CategoryGroups).filter_by(name="Outros").one()
    other = db.query(CategoryGroups).filter_by(name="Moradia").one()
    plants = Categories(name="Plantas", group_id=group.id, family_id=user.family_id)
    db.add(plants)
    db.commit()
    _plan(client, auth_headers, plants.id, 5000)

    client.patch(f"/categories/{plants.id}", json={"group_id": other.id}, headers=auth_headers)

    assert _row(_month(client, auth_headers), plants.id)["budgeted"] == 5000
    groups = {g["name"]: [c["id"] for c in g["categories"]] for g in _month(client, auth_headers)["groups"]}
    assert plants.id in groups["Moradia"]


def test_copying_skips_budgets_that_can_no_longer_be_seen(client, db, auth_headers, user):
    """A hidden budget (a category that went to an income group some other way) must not be copied, nor counted."""
    income = db.query(CategoryGroups).filter_by(name="Receitas").one()
    hidden = Categories(name="Antiga", group_id=income.id, family_id=user.family_id)
    db.add(hidden)
    db.commit()
    db.add(Budgets(family_id=user.family_id, category_id=hidden.id, month=date(2026, 11, 1), amount=100))
    db.commit()

    response = _copy(client, auth_headers)

    assert response.json()["data"]["copied"] == 0
    assert db.query(Budgets).count() == 1


def test_planning_and_copying_take_the_familys_lock_like_the_categories_do(client, auth_headers, food, monkeypatch):
    """Two members setting the same amount for the first time, or a category being deleted at that moment, must not
    end in a server error: the requests wait for each other on the family."""
    from api.controllers import budgets_controller

    locked = []
    real = budgets_controller.lock_family
    monkeypatch.setattr(
        budgets_controller, "lock_family", lambda db, family_id: (locked.append(family_id), real(db, family_id))
    )

    _plan(client, auth_headers, food, 100)
    _copy(client, auth_headers)

    assert len(locked) == 2

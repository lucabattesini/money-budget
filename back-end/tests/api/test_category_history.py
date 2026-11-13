"""One category over the months: what was planned and spent in each, and the month's transactions."""

from datetime import datetime

import pytest

from schemas.tables import Categories, CategoryGroups
from tests.conftest import MISSING_ID

NOV = "2026-11"


def _history(client, headers, category_id, month=NOV, months=None, show=None):
    params = {"month": month, **({"months": months} if months else {}), **({"show": show} if show else {})}
    response = client.get(f"/budgets/categories/{category_id}", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _plan(client, headers, category_id, amount, month):
    response = client.put(
        "/budgets", json={"category_id": str(category_id), "month": month, "amount": amount}, headers=headers
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def food(category_ids):
    return category_ids["Restaurantes e Bares"]


def test_gives_each_month_of_the_history_with_what_was_planned_and_spent(
    client, auth_headers, user, food, make_transaction
):
    _plan(client, auth_headers, food, 50000, "2026-09")
    _plan(client, auth_headers, food, 60000, "2026-11")
    make_transaction(user, food, value=1000, when=datetime(2026, 8, 20, 12))
    make_transaction(user, food, value=2000, when=datetime(2026, 9, 1, 0, 0))
    make_transaction(user, food, value=3000, when=datetime(2026, 9, 30, 23, 59))
    make_transaction(user, food, value=4000, when=datetime(2026, 11, 5, 12))

    data = _history(client, auth_headers, food, months=4)

    assert data["category"]["name"] == "Restaurantes e Bares"
    assert data["category"]["group_name"] == "Alimentação"
    assert data["month"] == NOV
    assert data["history"] == [
        {"month": "2026-08", "budgeted": None, "spent": 1000},  # before the first plan
        {"month": "2026-09", "budgeted": 50000, "spent": 5000},  # both edges of the month count
        {"month": "2026-10", "budgeted": 50000, "spent": 0},  # a plan stays in force
        {"month": "2026-11", "budgeted": 60000, "spent": 4000},  # until a later month changes it
    ]


def test_the_history_matches_what_the_budget_page_shows_for_the_month(
    client, auth_headers, user, food, make_transaction
):
    _plan(client, auth_headers, food, 50000, NOV)
    make_transaction(user, food, value=1500, when=datetime(2026, 11, 5, 12))
    make_transaction(user, food, value=700, when=datetime(2026, 11, 6, 12), excluded=True)  # left out of the totals
    make_transaction(user, food, value=900, when=datetime(2026, 11, 7, 12), type="credit")  # a refund is not spending

    page = client.get("/budgets", params={"month": NOV}, headers=auth_headers).json()["data"]
    shown = next(c for g in page["groups"] for c in g["categories"] if c["id"] == str(food))
    last = _history(client, auth_headers, food)["history"][-1]

    assert last == {"month": NOV, "budgeted": shown["budgeted"], "spent": shown["spent"]}
    assert last["spent"] == 1500


def test_lists_the_transactions_of_the_month_newest_first_with_the_person_and_marks_the_left_out_ones(
    client, auth_headers, user, food, make_transaction
):
    make_transaction(user, food, label="Pizza", value=4000, when=datetime(2026, 11, 3, 20))
    make_transaction(user, food, label="Café", value=900, when=datetime(2026, 11, 20, 8))
    make_transaction(
        user, food, label="Transferência interna", value=700, when=datetime(2026, 11, 10, 8), excluded=True
    )
    make_transaction(user, food, label="Estorno", value=500, when=datetime(2026, 11, 11, 8), type="credit")
    make_transaction(user, food, label="De outubro", value=100, when=datetime(2026, 10, 31, 23, 59))
    make_transaction(user, food, label="De dezembro", value=100, when=datetime(2026, 12, 1, 0, 0))

    data = _history(client, auth_headers, food)

    assert [t["label"] for t in data["transactions"]] == ["Café", "Transferência interna", "Pizza"]
    assert [t["excluded"] for t in data["transactions"]] == [False, True, False]
    assert {t["user_name"] for t in data["transactions"]} == {user.name}
    assert data["transactions"][0]["value"] == 900


def test_a_plan_removed_in_a_month_ends_the_plan_from_then_on(client, auth_headers, food):
    _plan(client, auth_headers, food, 50000, "2026-09")
    _plan(client, auth_headers, food, None, "2026-11")

    budgeted = [h["budgeted"] for h in _history(client, auth_headers, food, months=3)["history"]]

    assert budgeted == [50000, 50000, None]


def test_zero_is_a_plan_and_not_the_lack_of_one(client, auth_headers, food):
    _plan(client, auth_headers, food, 0, NOV)

    assert _history(client, auth_headers, food, months=2)["history"][-1]["budgeted"] == 0


def test_the_history_never_goes_before_the_year_2000(client, auth_headers, food):
    data = _history(client, auth_headers, food, month="2000-02", months=24)

    assert [h["month"] for h in data["history"]] == ["2000-01", "2000-02"]


def test_asks_for_six_months_unless_told_otherwise_and_refuses_silly_numbers(client, auth_headers, food):
    assert len(_history(client, auth_headers, food)["history"]) == 6
    for months in (0, 25, "abc"):
        response = client.get(
            f"/budgets/categories/{food}", params={"month": NOV, "months": months}, headers=auth_headers
        )
        assert response.status_code == 422
    assert (
        client.get(f"/budgets/categories/{food}", params={"month": "2026-13"}, headers=auth_headers).status_code == 422
    )


def test_never_shows_another_familys_spending_and_answers_404_for_what_it_cannot_show(
    client, db, auth_headers, user, other_user, headers_for, food, make_transaction
):
    make_transaction(user, food, label="Meu", value=1000, when=datetime(2026, 11, 3, 12))
    make_transaction(other_user, food, label="Deles", value=99900, when=datetime(2026, 11, 3, 12))
    own = Categories(
        name="Só deles",
        family_id=other_user.family_id,
        group_id=db.query(CategoryGroups).filter_by(name="Outros").one().id,
    )
    income = Categories(name="Salário", group_id=db.query(CategoryGroups).filter_by(name="Receitas").one().id)
    db.add_all([own, income])
    db.commit()

    mine = _history(client, auth_headers, food)
    theirs = _history(client, headers_for(other_user), food)

    assert [t["label"] for t in mine["transactions"]] == ["Meu"] and mine["history"][-1]["spent"] == 1000
    assert [t["label"] for t in theirs["transactions"]] == ["Deles"] and theirs["history"][-1]["spent"] == 99900
    for category_id in (own.id, MISSING_ID, income.id):  # another family's, missing, an income category
        response = client.get(f"/budgets/categories/{category_id}", params={"month": NOV}, headers=auth_headers)
        assert response.status_code == 404


def test_needs_a_login(client, food):
    assert client.get(f"/budgets/categories/{food}", params={"month": NOV}).status_code == 401


def test_can_list_the_transactions_of_an_earlier_month_while_the_history_stays_where_it_is(
    client, auth_headers, user, food, make_transaction
):
    make_transaction(user, food, label="De setembro", value=2000, when=datetime(2026, 9, 10, 12))
    make_transaction(user, food, label="De novembro", value=4000, when=datetime(2026, 11, 5, 12))

    data = _history(client, auth_headers, food, months=3, show="2026-09")

    assert data["transactions_month"] == "2026-09"
    assert [t["label"] for t in data["transactions"]] == ["De setembro"]
    assert [h["month"] for h in data["history"]] == ["2026-09", "2026-10", "2026-11"]  # the window did not move
    assert _history(client, auth_headers, food)["transactions_month"] == NOV

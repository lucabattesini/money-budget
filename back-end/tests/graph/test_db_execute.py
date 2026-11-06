from datetime import datetime

from graph.nodes import node_db_execute
from schemas.agents_schemas import ToolCall


def run(user, *calls):
    return node_db_execute({"user_id": user.id, "family_id": user.family_id, "query_tool_calls": list(calls)})[
        "db_results"
    ]


def summarize(**args):
    return ToolCall(name="summarize_transactions", args=args)


def list_(**args):
    return ToolCall(name="list_transactions", args=args)


def test_summarize_groups_by_category_and_converts_cents_to_reais(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Mercado", 10000)
    make_transaction(user, category_ids["Restaurantes e Bares"], "Padaria", 2550)
    make_transaction(user, category_ids["Transporte público"], "Uber", 1999)

    [result] = run(user, summarize(group_by="category"))

    rows = {r["category"]: r for r in result["result"]}
    assert rows["Restaurantes e Bares"] == {
        "category": "Restaurantes e Bares",
        "total": 125.5,
        "count": 2,
        "average": 62.75,
        "max": 100.0,
    }
    assert rows["Transporte público"]["total"] == 19.99
    assert [r["category"] for r in result["result"]] == [
        "Restaurantes e Bares",
        "Transporte público",
    ]  # biggest total first


def test_summarize_by_weekday_names_the_day(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Sem categoria"], "Sunday thing", 1000, datetime(2026, 3, 1, 10))

    [result] = run(user, summarize(group_by="weekday"))

    assert result["result"][0]["weekday"] == "domingo"


def test_summarize_by_month_reports_the_period(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Sem categoria"], "x", 1000, datetime(2026, 3, 1, 10))

    [result] = run(user, summarize(group_by="month"))

    assert result["result"][0]["period"] == "2026-03"


def test_summarize_only_counts_the_users_own_transactions(user, other_user, make_transaction, category_ids):
    make_transaction(user, category_ids["Restaurantes e Bares"], "mine", 1000)
    make_transaction(other_user, category_ids["Restaurantes e Bares"], "theirs", 50000)

    [result] = run(user, summarize(group_by="category"))

    assert [(r["category"], r["total"]) for r in result["result"]] == [("Restaurantes e Bares", 10.0)]


def test_list_returns_the_users_transactions_in_reais(user, other_user, make_transaction, category_ids):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Mine", 1250, datetime(2026, 3, 1))
    make_transaction(other_user, category_ids["Restaurantes e Bares"], "Not mine", 9999)

    [result] = run(user, list_(limit=10))

    assert result["result"] == [
        {"description": "Mine", "amount": 12.5, "date": "2026-03-01", "category": "Restaurantes e Bares"}
    ]


def test_a_summary_leaves_out_what_the_person_left_out_of_the_totals(user, make_transaction, category_ids):
    food = category_ids["Restaurantes e Bares"]
    make_transaction(user, food, "counted", 1000)
    make_transaction(user, food, "left out", 9000, excluded=True)

    [result] = run(user, summarize(group_by="category"))

    assert [(r["category"], r["total"], r["count"]) for r in result["result"]] == [("Restaurantes e Bares", 10.0, 1)]


def test_a_list_still_shows_a_left_out_transaction_and_says_it_is_not_counted(user, make_transaction, category_ids):
    food = category_ids["Restaurantes e Bares"]
    make_transaction(user, food, "counted", 1000, datetime(2026, 3, 2))
    make_transaction(user, food, "left out", 9000, datetime(2026, 3, 1), excluded=True)

    [result] = run(user, list_(limit=10))

    assert result["result"] == [
        {"description": "counted", "amount": 10.0, "date": "2026-03-02", "category": "Restaurantes e Bares"},
        {
            "description": "left out",
            "amount": 90.0,
            "date": "2026-03-01",
            "category": "Restaurantes e Bares",
            "left_out_of_totals": True,
        },
    ]


def test_category_filter_by_name(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Restaurantes e Bares"], "food", 1000)
    make_transaction(user, category_ids["Transporte público"], "bus", 500)

    [result] = run(user, list_(categories=["Transporte público"]))

    assert [r["description"] for r in result["result"]] == ["bus"]


def test_valid_category_missing_from_the_database_matches_nothing(user, make_transaction, category_ids):
    # "Pets" is a valid category name but is not seeded in the test database. It must
    # match nothing instead of silently widening the filter to every transaction.
    make_transaction(user, category_ids["Restaurantes e Bares"], "food", 1000)

    [result] = run(user, list_(categories=["Pets"]))

    assert result["result"] == []


def test_amount_filters_are_in_reais(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Sem categoria"], "small", 500)
    make_transaction(user, category_ids["Sem categoria"], "big", 5000)

    [result] = run(user, list_(min_amount=10.0))

    assert [r["description"] for r in result["result"]] == ["big"]


def test_invalid_category_name_is_reported_not_raised(user):
    [result] = run(user, list_(categories=["Does not exist"]))

    assert result == {"tool": "list_transactions", "error": "Invalid filters"}


def test_unknown_tool_is_reported(user):
    [result] = run(user, ToolCall(name="drop_everything", args={}))

    assert result == {"tool": "drop_everything", "error": "Unknown tool"}


def test_several_tool_calls_return_one_result_each_in_order(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Sem categoria"], "x", 1000)

    results = run(user, summarize(), list_())

    assert [r["tool"] for r in results] == ["summarize_transactions", "list_transactions"]


def test_a_category_name_only_matches_the_askers_own_or_default_categories(
    db, user, other_user, make_transaction, category_ids
):
    from schemas.tables import Categories

    theirs = Categories(name="Pets", family_id=other_user.family_id)
    db.add(theirs)
    db.commit()
    make_transaction(other_user, theirs.id, "Ração", 7000)
    make_transaction(user, category_ids["Sem categoria"], "mine", 1000)

    [result] = run(user, list_(categories=["Pets"]))

    assert result["result"] == []  # the other family's "Pets" is not theirs to filter by

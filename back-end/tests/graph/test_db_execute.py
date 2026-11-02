from datetime import datetime

from graph.nodes import node_db_execute
from schemas.agents_schemas import ToolCall


def run(user, *calls):
    return node_db_execute({"user_id": user.id, "query_tool_calls": list(calls)})["db_results"]


def summarize(**args):
    return ToolCall(name="summarize_transactions", args=args)


def list_(**args):
    return ToolCall(name="list_transactions", args=args)


def test_summarize_groups_by_category_and_converts_cents_to_reais(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], "Mercado", 10000)
    make_transaction(user, category_ids["Alimentação"], "Padaria", 2550)
    make_transaction(user, category_ids["Transporte"], "Uber", 1999)

    [result] = run(user, summarize(group_by="category"))

    rows = {r["category"]: r for r in result["result"]}
    assert rows["Alimentação"] == {
        "category": "Alimentação",
        "total": 125.5,
        "count": 2,
        "average": 62.75,
        "max": 100.0,
    }
    assert rows["Transporte"]["total"] == 19.99
    assert [r["category"] for r in result["result"]] == ["Alimentação", "Transporte"]  # biggest total first


def test_summarize_by_weekday_names_the_day(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Outros"], "Sunday thing", 1000, datetime(2026, 3, 1, 10))

    [result] = run(user, summarize(group_by="weekday"))

    assert result["result"][0]["weekday"] == "domingo"


def test_summarize_by_month_reports_the_period(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Outros"], "x", 1000, datetime(2026, 3, 1, 10))

    [result] = run(user, summarize(group_by="month"))

    assert result["result"][0]["period"] == "2026-03"


def test_summarize_only_counts_the_users_own_transactions(user, other_user, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], "mine", 1000)
    make_transaction(other_user, category_ids["Alimentação"], "theirs", 50000)

    [result] = run(user, summarize(group_by="category"))

    assert [(r["category"], r["total"]) for r in result["result"]] == [("Alimentação", 10.0)]


def test_list_returns_the_users_transactions_in_reais(user, other_user, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], "Mine", 1250, datetime(2026, 3, 1))
    make_transaction(other_user, category_ids["Alimentação"], "Not mine", 9999)

    [result] = run(user, list_(limit=10))

    assert result["result"] == [
        {"description": "Mine", "amount": 12.5, "date": "2026-03-01", "category": "Alimentação"}
    ]


def test_category_filter_by_name(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], "food", 1000)
    make_transaction(user, category_ids["Transporte"], "bus", 500)

    [result] = run(user, list_(categories=["Transporte"]))

    assert [r["description"] for r in result["result"]] == ["bus"]


def test_valid_category_missing_from_the_database_matches_nothing(user, make_transaction, category_ids):
    # "Pets" is a valid category name but is not seeded in the test database. It must
    # match nothing instead of silently widening the filter to every transaction.
    make_transaction(user, category_ids["Alimentação"], "food", 1000)

    [result] = run(user, list_(categories=["Pets"]))

    assert result["result"] == []


def test_amount_filters_are_in_reais(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Outros"], "small", 500)
    make_transaction(user, category_ids["Outros"], "big", 5000)

    [result] = run(user, list_(min_amount=10.0))

    assert [r["description"] for r in result["result"]] == ["big"]


def test_invalid_category_name_is_reported_not_raised(user):
    [result] = run(user, list_(categories=["Does not exist"]))

    assert result == {"tool": "list_transactions", "error": "Invalid filters"}


def test_unknown_tool_is_reported(user):
    [result] = run(user, ToolCall(name="drop_everything", args={}))

    assert result == {"tool": "drop_everything", "error": "Unknown tool"}


def test_several_tool_calls_return_one_result_each_in_order(user, make_transaction, category_ids):
    make_transaction(user, category_ids["Outros"], "x", 1000)

    results = run(user, summarize(), list_())

    assert [r["tool"] for r in results] == ["summarize_transactions", "list_transactions"]

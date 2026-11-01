from datetime import datetime

from graph.nodes import node_db_execute
from schemas.agents_schemas import ToolCall
from schemas.tables import TransactionDB


def _add(db, user, category_id, label, value):
    db.add(TransactionDB(user_id=user.id, label=label, value=value, date=datetime.now(), category_id=category_id))
    db.commit()


def test_summarize_converts_cents_to_reais(db, user, category_id):
    _add(db, user, category_id, "Mercado", 10000)
    _add(db, user, category_id, "Padaria", 2550)
    call = ToolCall(name="summarize_transactions", args={"group_by": "category"})

    result = node_db_execute({"user_id": user.id, "query_tool_calls": [call]})["db_results"][0]

    row = result["result"][0]
    assert (row["category"], row["total"], row["count"]) == ("Alimentação", 125.5, 2)


def test_list_returns_the_users_transactions(db, user, other_user, category_id):
    _add(db, user, category_id, "Mine", 1000)
    _add(db, other_user, category_id, "Not mine", 9999)
    call = ToolCall(name="list_transactions", args={"limit": 10})

    result = node_db_execute({"user_id": user.id, "query_tool_calls": [call]})["db_results"][0]

    assert [r["description"] for r in result["result"]] == ["Mine"]


def test_invalid_filters_are_reported_not_raised(user):
    call = ToolCall(name="list_transactions", args={"categories": ["Does not exist"]})

    result = node_db_execute({"user_id": user.id, "query_tool_calls": [call]})["db_results"][0]

    assert result == {"tool": "list_transactions", "error": "Invalid filters"}

"""The whole chatbot graph, with only the four Gemini-backed agents stubbed."""

import json
from datetime import datetime

import pytest

import graph.nodes as nodes
from graph.graph import app, route_intent
from schemas.agents_schemas import (
    ExpenseItem,
    OrchestratorResponse,
    QueryResponse,
    RecorderResponse,
    SecretaryResponse,
    ToolCall,
)
from schemas.tables import TransactionDB


@pytest.fixture
def agents(monkeypatch):
    """Script each agent; records what the next one received."""
    seen = {}

    def script(intent, recorder=None, query_calls=None, secretary_reply="ok"):
        monkeypatch.setattr(nodes, "run_orchestrator", lambda m: OrchestratorResponse(message=m, type=intent))
        monkeypatch.setattr(nodes, "run_recorder", lambda m: recorder or RecorderResponse(items=[]))
        monkeypatch.setattr(nodes, "run_query", lambda m: QueryResponse(tool_calls=query_calls or []))

        def secretary(message, results):
            seen["secretary_message"] = message
            seen["secretary_results"] = json.loads(results)
            return SecretaryResponse(reply=secretary_reply)

        monkeypatch.setattr(nodes, "run_secretary", secretary)

    script.seen = seen
    return script


def ask(user, message="oi"):
    return app.invoke({"user_message": message, "user_id": user.id, "family_id": user.family_id})


@pytest.mark.parametrize(
    "intent, destination",
    [
        ("registry", "recorder"),
        ("check", "query"),
        ("off-topic", "off_topic"),
        ("something-new", "off_topic"),
        (None, "off_topic"),
    ],
)
def test_intent_routing(intent, destination):
    assert route_intent({"intent": intent}) == destination


def test_registering_an_expense_saves_it_and_confirms(db, user, agents):
    agents(
        "registry",
        recorder=RecorderResponse(items=[ExpenseItem(amount=25.5, category="Transporte público", description="Uber")]),
    )

    result = ask(user, "gastei 25,50 de uber")

    assert result["final_response"].startswith("Registrado!")
    assert "R$ 25,50" in result["final_response"]
    [row] = db.query(TransactionDB).all()
    assert (row.user_id, row.family_id, row.value, row.label) == (user.id, user.family_id, 2550, "Uber")


def test_asking_a_question_reads_the_users_data_and_answers_through_the_secretary(
    user, other_user, make_transaction, category_ids, agents
):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Mercado", 12000, datetime(2026, 3, 1))
    make_transaction(other_user, category_ids["Restaurantes e Bares"], "Not mine", 99999, datetime(2026, 3, 1))
    agents(
        "check",
        query_calls=[ToolCall(name="summarize_transactions", args={"group_by": "category"})],
        secretary_reply="Você gastou R$ 120,00 com alimentação.",
    )

    result = ask(user, "quanto gastei com comida?")

    assert result["final_response"] == "Você gastou R$ 120,00 com alimentação."
    assert agents.seen["secretary_message"] == "quanto gastei com comida?"
    [summary] = agents.seen["secretary_results"]
    assert summary["tool"] == "summarize_transactions"
    assert [(r["category"], r["total"]) for r in summary["result"]] == [("Restaurantes e Bares", 120.0)]


def test_off_topic_messages_get_the_fixed_refusal_and_touch_nothing(db, user, agents):
    agents("off-topic")

    result = ask(user, "qual a capital da França?")

    assert result["final_response"] == "Desculpe, só consigo te ajudar com suas finanças."
    assert db.query(TransactionDB).count() == 0

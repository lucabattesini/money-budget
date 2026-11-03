from datetime import date, timedelta

import pytest

import graph.nodes as nodes
from graph.nodes import node_recorder
from schemas.agents_schemas import ExpenseItem, RecorderResponse
from schemas.tables import TransactionDB


def item(amount=10.0, category="Restaurantes e Bares", description="Almoço", when=None):
    return ExpenseItem(amount=amount, category=category, description=description, date=when)


@pytest.fixture
def recorder(monkeypatch):
    """Stub the Gemini-backed recorder agent with a canned response."""

    def _set(items=(), reply=None):
        monkeypatch.setattr(
            nodes, "run_recorder", lambda message, **kw: RecorderResponse(items=list(items), reply=reply)
        )

    return _set


def run(user):
    return node_recorder({"user_message": "irrelevant", "user_id": user.id, "family_id": user.family_id})


def rows(db):
    return db.query(TransactionDB).order_by(TransactionDB.id).all()


@pytest.mark.parametrize("amount, cents", [(12.5, 1250), (19.99, 1999), (0.29, 29), (1234.56, 123456), (0.01, 1)])
def test_amounts_are_stored_as_exact_cents(db, user, recorder, amount, cents):
    recorder([item(amount)])

    run(user)

    assert rows(db)[0].value == cents


def test_the_expense_is_saved_for_the_right_user_and_category(db, user, other_user, recorder, category_ids):
    recorder([item(30.0, "Transporte público", "Uber")])

    run(user)

    [row] = rows(db)
    assert (row.user_id, row.family_id, row.label, row.category_id) == (
        user.id,
        user.family_id,
        "Uber",
        category_ids["Transporte público"],
    )


def test_the_reply_confirms_each_expense_in_brazilian_format(db, user, recorder):
    recorder(
        [
            item(1234.56, "Aluguel", "Aluguel de março", date(2026, 3, 5)),
            item(7.0, "Transporte público", "Ônibus", date(2026, 3, 6)),
        ]
    )

    reply = run(user)["final_response"]

    assert reply.startswith("Registrado!")
    assert "R$ 1.234,56 em Aluguel (Aluguel de março, 05/03)" in reply
    assert "R$ 7,00 em Transporte público (Ônibus, 06/03)" in reply
    assert len(rows(db)) == 2


def test_a_past_date_is_kept(db, user, recorder):
    recorder([item(when=date(2026, 1, 15))])

    run(user)

    assert rows(db)[0].transactioned_at.date() == date(2026, 1, 15)


def test_a_missing_date_means_today(db, user, recorder):
    recorder([item(when=None)])

    run(user)

    assert rows(db)[0].transactioned_at.date() == date.today()


def test_a_future_date_is_clamped_to_today(db, user, recorder):
    recorder([item(when=date.today() + timedelta(days=30))])

    run(user)

    assert rows(db)[0].transactioned_at.date() == date.today()


def test_a_valid_category_missing_from_the_database_falls_back_to_sem_categoria(db, user, recorder, category_ids):
    recorder([item(category="Pets", description="Ração")])  # "Pets" is not seeded in the test database

    reply = run(user)["final_response"]

    assert rows(db)[0].category_id == category_ids["Sem categoria"]
    assert "em Sem categoria" in reply


def test_the_agents_text_is_added_after_the_confirmation(db, user, recorder):
    recorder([item()], reply="Quer registrar mais algum?")

    reply = run(user)["final_response"]

    assert reply.startswith("Registrado!")
    assert reply.endswith("Quer registrar mais algum?")


def test_when_nothing_was_extracted_the_agents_reply_is_returned_and_nothing_saved(db, user, recorder):
    recorder([], reply="Quanto foi o gasto?")

    assert run(user)["final_response"] == "Quanto foi o gasto?"
    assert rows(db) == []


def test_when_nothing_was_extracted_and_no_reply_the_user_is_asked_for_the_amount(db, user, recorder):
    recorder([], reply=None)

    reply = run(user)["final_response"]

    assert "Não encontrei nenhum gasto" in reply
    assert rows(db) == []


def test_extracted_items_are_returned_in_the_state(db, user, recorder):
    expenses = [item(5.0), item(6.0)]
    recorder(expenses)

    assert run(user)["extracted_items"] == expenses


def test_the_assistant_finds_a_category_whose_name_starts_with_an_emoji(db, user, recorder, category_ids):
    """Defaults are stored as "🛒 Supermercado", but the assistant works with the words only."""
    from schemas.tables import Categories, CategoryGroups

    group = db.query(CategoryGroups).filter_by(name="Alimentação").one()
    db.query(Categories).filter_by(id=category_ids["Supermercado"]).update({"name": "🛒 Supermercado"})
    db.add(Categories(name="🌱 Pets", family_id=user.family_id, group_id=group.id))
    db.commit()
    recorder([item(30.0, "Supermercado", "Compras da semana"), item(10.0, "Pets", "Ração")])

    run(user)

    by_label = {r.label: r.category_id for r in rows(db)}
    assert by_label["Compras da semana"] == category_ids["Supermercado"]
    own = db.query(Categories).filter_by(name="🌱 Pets").one()
    assert by_label["Ração"] == own.id  # the family's own category wins over a default of the same words

"""A transaction can be left out of the totals (TKT-87): still listed and exported, never counted."""

from datetime import datetime

import pytest

from api.repositories.transactions_repo import aggregate_transactions, create_transaction
from schemas.tables import Categories, CategoryGroups, TransactionDB
from schemas.tables_schemas import Transaction, TransactionFilters
from tests.conftest import MISSING_ID

NOV = datetime(2026, 11, 10, 12, 0)


@pytest.fixture
def transfer(db):
    """The default category "Transferência" of the group "Transferências"."""
    group = db.query(CategoryGroups).filter_by(name="Transferências").one()
    category = Categories(name="🔄 Transferência", group_id=group.id)
    db.add(category)
    db.commit()
    return category


@pytest.fixture
def card_payment(db):
    group = db.query(CategoryGroups).filter_by(name="Transferências").one()
    category = Categories(name="💳 Pagamento de fatura do cartão", group_id=group.id)
    db.add(category)
    db.commit()
    return category


@pytest.fixture
def adjustment(db):
    group = db.query(CategoryGroups).filter_by(name="Transferências").one()
    category = Categories(name="🧮 Ajustes de saldo", group_id=group.id)
    db.add(category)
    db.commit()
    return category


def _create(client, headers, category_id, **fields):
    body = {"label": "x", "value": 1000, "category_id": category_id, **fields}
    response = client.post("/transactions/create", json=body, headers=headers)
    assert response.status_code == 201, response.text


def _listed(client, headers):
    return {t["label"]: t for t in client.post("/transactions/", json={}, headers=headers).json()["data"]}


# --- what is left out by default ---------------------------------------------------------------------------------------


def test_a_transfer_and_a_card_payment_start_out_left_out_and_a_purchase_does_not(
    client, auth_headers, category_ids, transfer, card_payment, adjustment
):
    _create(client, auth_headers, str(transfer.id), label="transfer")
    _create(client, auth_headers, str(card_payment.id), label="card")
    _create(client, auth_headers, str(adjustment.id), label="adjustment")  # a correction: counts
    _create(client, auth_headers, category_ids["Supermercado"], label="food")

    left_out = {label: t["excluded"] for label, t in _listed(client, auth_headers).items()}

    assert left_out == {"transfer": True, "card": True, "adjustment": False, "food": False}


def test_the_person_can_override_the_default_when_creating(client, auth_headers, category_ids, transfer):
    _create(client, auth_headers, str(transfer.id), label="counted transfer", excluded=False)
    _create(client, auth_headers, category_ids["Supermercado"], label="left out purchase", excluded=True)

    left_out = {label: t["excluded"] for label, t in _listed(client, auth_headers).items()}

    assert left_out == {"counted transfer": False, "left out purchase": True}


def test_the_assistant_records_a_transfer_as_left_out_too(db, user, transfer):
    """The chatbot creates through the same repository function, with nothing said about the totals."""
    create_transaction(
        db,
        Transaction(label="para a poupança", value=5000, category_id=transfer.id, transactioned_at=NOV),
        user.family_id,
        user.id,
    )

    assert db.query(TransactionDB).one().excluded is True


# --- marking and unmarking ---------------------------------------------------------------------------------------------


def _update(client, headers, transaction_id, **fields):
    body = {"label": "x", "value": 1000, "category_id": fields.pop("category_id"), **fields}
    return client.put(f"/transactions/{transaction_id}", json=body, headers=headers)


def test_a_transaction_can_be_marked_and_unmarked(client, db, user, auth_headers, category_ids, make_transaction):
    row = make_transaction(user, category_ids["Supermercado"])
    category = str(category_ids["Supermercado"])

    marked = _update(client, auth_headers, row.id, category_id=category, excluded=True)
    assert (marked.status_code, marked.json()["data"]["excluded"]) == (200, True)
    db.refresh(row)
    assert row.excluded is True

    unmarked = _update(client, auth_headers, row.id, category_id=category, excluded=False)
    assert (unmarked.status_code, unmarked.json()["data"]["excluded"]) == (200, False)


def test_editing_without_saying_anything_about_the_totals_keeps_it_as_it_was(
    client, db, user, auth_headers, category_ids, make_transaction
):
    row = make_transaction(user, category_ids["Supermercado"], excluded=True)

    assert _update(client, auth_headers, row.id, category_id=str(category_ids["Supermercado"])).status_code == 200

    db.refresh(row)
    assert row.excluded is True


def test_another_familys_transaction_cannot_be_marked(
    client, db, auth_headers, other_user, category_ids, make_transaction
):
    theirs = make_transaction(other_user, category_ids["Supermercado"])

    response = _update(client, auth_headers, theirs.id, category_id=str(category_ids["Supermercado"]), excluded=True)

    assert response.status_code == 404
    db.refresh(theirs)
    assert theirs.excluded is False
    assert _update(client, auth_headers, MISSING_ID, category_id=str(category_ids["Supermercado"])).status_code == 404


# --- never counted -----------------------------------------------------------------------------------------------------


def test_a_left_out_transaction_is_still_listed_but_not_summed(
    client, user, auth_headers, category_ids, make_transaction
):
    food = category_ids["Supermercado"]
    make_transaction(user, food, label="counted", value=1000)
    make_transaction(user, food, label="left out", value=9000, excluded=True)

    listed = _listed(client, auth_headers)
    summed = client.post("/transactions/summed-by-category", json={}, headers=auth_headers).json()["data"]

    assert set(listed) == {"counted", "left out"}  # the list shows both
    assert summed == [{"category_id": str(food), "total": 1000}]  # the sum counts one


def test_a_left_out_transaction_is_not_in_the_budget(client, user, auth_headers, category_ids, make_transaction):
    food = category_ids["Supermercado"]
    make_transaction(user, food, value=1000, when=NOV)
    make_transaction(user, food, value=9000, when=NOV, excluded=True)

    data = client.get("/budgets", params={"month": "2026-11"}, headers=auth_headers).json()["data"]

    spent = [c["spent"] for g in data["groups"] for c in g["categories"] if c["id"] == str(food)]
    assert spent == [1000]


def test_the_assistants_totals_leave_it_out(db, user, category_ids, make_transaction):
    food = category_ids["Supermercado"]
    make_transaction(user, food, value=1000, when=NOV)
    make_transaction(user, food, value=9000, when=NOV, excluded=True)

    everything = aggregate_transactions(db, user.family_id, TransactionFilters())
    by_category = aggregate_transactions(db, user.family_id, TransactionFilters(), group_by="category")
    by_month = aggregate_transactions(db, user.family_id, TransactionFilters(), group_by="month")

    assert (everything[0].total, everything[0].count) == (1000, 1)
    assert [(r.total, r.count) for r in by_category] == [(1000, 1)]
    assert [(r.total, r.count) for r in by_month] == [(1000, 1)]


def test_one_familys_marks_never_change_anothers_totals(
    client, user, other_user, auth_headers, category_ids, make_transaction
):
    food = category_ids["Supermercado"]
    make_transaction(user, food, value=1000)
    make_transaction(other_user, food, value=7000, excluded=True)

    summed = client.post("/transactions/summed-by-category", json={}, headers=auth_headers).json()["data"]

    assert summed == [{"category_id": str(food), "total": 1000}]


# --- export and import ---------------------------------------------------------------------------------------------------


def _csv(*lines, header="Data;Descrição;Categoria;Valor;Tipo;Fora dos totais"):
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


def _import(client, queue, headers, content):
    uploaded = client.post(
        "/imports", files={"file": ("t.csv", content, "application/octet-stream")}, headers=headers
    ).json()["data"]
    assert uploaded["suggested_map"]["Fora dos totais"] is not None  # found by its name, like the other columns
    checked = client.put(
        f"/imports/{uploaded['id']}/columns", json={"mapping": uploaded["suggested_map"]}, headers=headers
    )
    assert checked.status_code == 200, checked.text
    assert client.post(f"/imports/{uploaded['id']}/start", headers=headers).status_code == 202
    queue.run()
    return client.get(f"/imports/{uploaded['id']}", headers=headers).json()["data"]


@pytest.fixture
def queue(monkeypatch):
    from api.controllers import imports_controller
    from api.routers import imports_router

    pending = []
    monkeypatch.setattr(imports_router, "run_import_job", pending.append)

    class Queue:
        @staticmethod
        def run():
            while pending:
                imports_controller.run_import_job(pending.pop(0))

    return Queue()


def test_an_imported_file_can_say_which_rows_are_left_out(client, db, user, auth_headers, queue, category_ids):
    job = _import(
        client,
        queue,
        auth_headers,
        _csv(
            "15/03/2026;a;Supermercado;10,00;Débito;Sim",
            "15/03/2026;b;Supermercado;20,00;Débito;Não",
            "15/03/2026;c;Supermercado;30,00;Débito;",  # nothing said: the category's default (counts)
        ),
    )

    assert job["status"] == "done"
    assert {t.label: t.excluded for t in db.query(TransactionDB)} == {"a": True, "b": False, "c": False}


def test_an_imported_transfer_is_left_out_unless_the_file_says_otherwise(
    client, db, auth_headers, queue, transfer, card_payment
):
    _import(
        client,
        queue,
        auth_headers,
        _csv(
            "15/03/2026;a;Transferência;10,00;Débito;",
            "15/03/2026;b;Pagamento de fatura do cartão;20,00;Débito;",
            "15/03/2026;c;Transferência;30,00;Débito;Não",
        ),
    )

    assert {t.label: t.excluded for t in db.query(TransactionDB)} == {"a": True, "b": True, "c": False}


def test_a_value_that_is_neither_yes_nor_no_is_a_problem_of_that_row(client, auth_headers, category_ids):
    uploaded = client.post(
        "/imports",
        files={"file": ("t.csv", _csv("15/03/2026;a;Supermercado;10,00;Débito;talvez"), "text/csv")},
        headers=auth_headers,
    ).json()["data"]

    response = client.put(
        f"/imports/{uploaded['id']}/columns", json={"mapping": uploaded["suggested_map"]}, headers=auth_headers
    )

    assert response.status_code == 422
    assert [(p["row"], p["message"]) for p in response.json()["problems"]] == [
        (2, '"Fora dos totais" precisa ser Sim ou Não.')
    ]


def test_the_export_says_which_transactions_are_left_out_and_can_be_imported_back(
    client, db, user, auth_headers, queue, category_ids, make_transaction
):
    from api.repositories.transactions_repo import list_all_transactions
    from api.services.export_service import build_transactions_table

    food = category_ids["Supermercado"]
    make_transaction(user, food, label="counted", value=1000, when=datetime(2026, 3, 15, 12))
    make_transaction(user, food, label="left out", value=2000, when=datetime(2026, 3, 16, 12), excluded=True)
    table = build_transactions_table(list_all_transactions(db, user.family_id))
    assert {row[1]: row[6] for row in table.rows} == {"counted": "Não", "left out": "Sim"}

    lines = [";".join([_cell(c) for c in table.columns])] + [";".join(_cell(c) for c in row) for row in table.rows]
    db.query(TransactionDB).delete()
    db.commit()
    _import(client, queue, auth_headers, ("\n".join(lines) + "\n").encode("utf-8"))

    assert {t.label: t.excluded for t in db.query(TransactionDB)} == {"counted": False, "left out": True}


def _cell(value):
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    if hasattr(value, "quantize"):  # a Decimal of reais
        return f"{value:.2f}".replace(".", ",")
    return str(value)

from datetime import datetime

import pytest

from schemas.tables import TransactionDB


def _create(client, headers, category_id, label="Almoço", value=2500):
    return client.post(
        "/transactions/create",
        json={"label": label, "value": value, "category_id": category_id},
        headers=headers,
    )


def _list(client, headers, body=None):
    response = client.post("/transactions/", json=body or {}, headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def _summed(client, headers, body=None):
    response = client.post("/transactions/summed-by-category", json=body or {}, headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


# --- create ----------------------------------------------------------------


def test_create_stores_the_transaction_for_the_caller(client, db, user, auth_headers, category_ids):
    response = _create(client, auth_headers, category_ids["Alimentação"], label="Almoço", value=2500)

    assert response.status_code == 201
    row = db.query(TransactionDB).one()
    assert (row.user_id, row.label, row.value, row.category_id) == (
        user.id,
        "Almoço",
        2500,
        category_ids["Alimentação"],
    )
    assert row.transactioned_at is not None


def test_create_requires_authentication(client, db, category_ids):
    response = client.post(
        "/transactions/create", json={"label": "x", "value": 1, "category_id": category_ids["Outros"]}
    )

    assert response.status_code == 401
    assert db.query(TransactionDB).count() == 0


def test_create_rejects_a_missing_label(client, db, auth_headers, category_ids):
    response = client.post(
        "/transactions/create", json={"value": 100, "category_id": category_ids["Outros"]}, headers=auth_headers
    )

    assert response.status_code == 422
    assert db.query(TransactionDB).count() == 0


# --- list ------------------------------------------------------------------


def test_list_returns_only_the_callers_transactions(
    client, user, other_user, auth_headers, headers_for, make_transaction, category_ids
):
    make_transaction(user, category_ids["Alimentação"], label="Mine", value=1000)
    make_transaction(other_user, category_ids["Alimentação"], label="Theirs", value=9999)

    mine = _list(client, auth_headers)
    theirs = _list(client, headers_for(other_user))

    assert [(t["label"], t["value"]) for t in mine] == [("Mine", 1000)]
    assert [(t["label"], t["value"]) for t in theirs] == [("Theirs", 9999)]


def test_list_is_newest_first(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="old", when=datetime(2026, 1, 10))
    make_transaction(user, cat, label="new", when=datetime(2026, 3, 10))
    make_transaction(user, cat, label="mid", when=datetime(2026, 2, 10))

    assert [t["label"] for t in _list(client, auth_headers)] == ["new", "mid", "old"]


def test_list_can_be_filtered_by_year(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="2025", when=datetime(2025, 6, 1))
    make_transaction(user, cat, label="2026", when=datetime(2026, 6, 1))

    rows = _list(client, auth_headers, {"organized_by": "year", "date": "2026-06-01T00:00:00"})

    assert [t["label"] for t in rows] == ["2026"]


def test_list_can_be_filtered_by_month_within_one_year(client, user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, label="march", when=datetime(2026, 3, 5))
    make_transaction(user, cat, label="april", when=datetime(2026, 4, 5))

    rows = _list(client, auth_headers, {"organized_by": "month", "date": "2026-03-01T00:00:00"})

    assert [t["label"] for t in rows] == ["march"]


# --- summed by category ----------------------------------------------------


def test_summed_groups_totals_per_category(client, user, auth_headers, make_transaction, category_ids):
    food, transport = category_ids["Alimentação"], category_ids["Transporte"]
    make_transaction(user, food, value=1000)
    make_transaction(user, food, value=2500)
    make_transaction(user, transport, value=700)

    rows = _summed(client, auth_headers)

    assert {r["category_id"]: r["total"] for r in rows} == {food: 3500, transport: 700}


def test_summed_ignores_other_users(client, user, other_user, auth_headers, make_transaction, category_ids):
    cat = category_ids["Alimentação"]
    make_transaction(user, cat, value=1000)
    make_transaction(other_user, cat, value=50_000)

    assert _summed(client, auth_headers) == [{"category_id": cat, "total": 1000}]


def test_summed_is_empty_without_transactions(client, auth_headers):
    assert _summed(client, auth_headers) == []


# --- delete ----------------------------------------------------------------


def test_delete_removes_the_callers_transaction(client, db, user, auth_headers, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    response = client.delete(f"/transactions/{row.id}", headers=auth_headers)

    assert response.status_code == 202
    assert db.query(TransactionDB).count() == 0


def test_delete_cannot_remove_another_users_transaction(
    client, db, user, other_user, headers_for, make_transaction, category_ids
):
    theirs = make_transaction(other_user, category_ids["Alimentação"], label="Theirs")

    response = client.delete(f"/transactions/{theirs.id}", headers=headers_for(user))

    assert response.status_code == 404
    assert db.query(TransactionDB).filter_by(id=theirs.id).count() == 1


def test_delete_of_an_unknown_id_reports_not_found(client, auth_headers):
    response = client.delete("/transactions/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_delete_requires_authentication(client, user, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    assert client.delete(f"/transactions/{row.id}").status_code == 401


# --- credit and debit -------------------------------------------------------


def test_a_transaction_is_a_debit_unless_said_otherwise(client, db, auth_headers, category_ids):
    _create(client, auth_headers, category_ids["Alimentação"])

    assert db.query(TransactionDB).one().type == "debit"
    assert _list(client, auth_headers)[0]["type"] == "debit"


def test_a_credit_is_stored_as_a_positive_amount_in_cents(client, db, auth_headers, category_ids):
    response = client.post(
        "/transactions/create",
        json={"label": "Salário", "value": 150000, "category_id": category_ids["Alimentação"], "type": "credit"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    saved = db.query(TransactionDB).one()
    assert (saved.type, saved.value) == ("credit", 150000)
    assert _list(client, auth_headers)[0]["type"] == "credit"


def test_create_rejects_an_unknown_type(client, db, auth_headers, category_ids):
    response = client.post(
        "/transactions/create",
        json={"label": "x", "value": 100, "category_id": category_ids["Alimentação"], "type": "refund"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert db.query(TransactionDB).count() == 0


def test_spending_totals_by_category_ignore_credits(client, user, auth_headers, make_transaction, category_ids):
    food = category_ids["Alimentação"]
    make_transaction(user, food, value=1000, type="debit")
    make_transaction(user, food, value=300, type="debit")
    make_transaction(user, food, value=99999, type="credit")

    assert _summed(client, auth_headers) == [{"category_id": food, "total": 1300}]


# --- dates: transactioned_at, created_at, updated_at -------------------------


def test_a_new_transaction_happens_now_and_records_when_it_was_saved(client, db, auth_headers, category_ids):
    before = datetime.now()
    _create(client, auth_headers, category_ids["Alimentação"])

    row = db.query(TransactionDB).one()
    assert row.transactioned_at >= before
    assert row.created_at is not None
    assert row.updated_at is None  # never edited


def test_create_accepts_the_date_the_transaction_happened(client, db, auth_headers, category_ids):
    response = client.post(
        "/transactions/create",
        json={
            "label": "Aluguel",
            "value": 100000,
            "category_id": category_ids["Alimentação"],
            "transactioned_at": "2026-01-05T10:30:00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    row = db.query(TransactionDB).one()
    assert row.transactioned_at == datetime(2026, 1, 5, 10, 30)
    assert row.created_at > row.transactioned_at  # saved later than it happened


def test_the_list_shows_all_three_dates(client, user, auth_headers, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], when=datetime(2026, 1, 5, 10, 30))

    row = _list(client, auth_headers)[0]

    assert row["transactioned_at"].startswith("2026-01-05T10:30")
    assert row["created_at"] is not None
    assert row["updated_at"] is None


def test_update_can_change_the_date_and_marks_the_row_as_edited(
    client, db, user, auth_headers, make_transaction, category_ids
):
    food = category_ids["Alimentação"]
    row = make_transaction(user, food, when=datetime(2026, 3, 15, 9, 0))
    created = row.created_at

    response = _update(client, auth_headers, row.id, category_id=food, transactioned_at="2026-02-01T08:00:00")

    assert response.status_code == 200
    db.expire_all()
    saved = db.query(TransactionDB).filter_by(id=row.id).one()
    assert saved.transactioned_at == datetime(2026, 2, 1, 8, 0)
    assert saved.created_at == created  # when it was first saved never changes
    assert saved.updated_at is not None and saved.updated_at >= created


def test_update_keeps_the_date_when_none_is_sent(client, db, user, auth_headers, make_transaction, category_ids):
    food = category_ids["Alimentação"]
    row = make_transaction(user, food, when=datetime(2026, 3, 15, 9, 0))

    _update(client, auth_headers, row.id, category_id=food)

    db.expire_all()
    assert db.query(TransactionDB).filter_by(id=row.id).one().transactioned_at == datetime(2026, 3, 15, 9, 0)


# --- update ----------------------------------------------------------------


def _update(client, headers, id, **fields):
    body = {"label": "Novo", "value": 3000, "category_id": None, **fields}
    return client.put(f"/transactions/{id}", json=body, headers=headers)


def test_update_changes_label_amount_and_category_and_keeps_the_date(
    client, db, user, auth_headers, make_transaction, category_ids
):
    row = make_transaction(user, category_ids["Alimentação"], label="Velho", value=1000)
    original_date = row.transactioned_at

    response = _update(client, auth_headers, row.id, label="Novo", value=3050, category_id=category_ids["Transporte"])

    assert response.status_code == 200
    assert response.json()["data"]["label"] == "Novo"
    db.expire_all()
    saved = db.query(TransactionDB).filter_by(id=row.id).one()
    assert (saved.label, saved.value, saved.category_id) == ("Novo", 3050, category_ids["Transporte"])
    assert saved.transactioned_at == original_date
    assert saved.user_id == user.id


def test_update_can_switch_between_credit_and_debit_and_keeps_the_type_when_omitted(
    client, db, user, auth_headers, make_transaction, category_ids
):
    food = category_ids["Alimentação"]
    row = make_transaction(user, food, type="debit")

    _update(client, auth_headers, row.id, category_id=food, type="credit")
    db.expire_all()
    assert db.query(TransactionDB).filter_by(id=row.id).one().type == "credit"

    _update(client, auth_headers, row.id, category_id=food)  # no type: unchanged
    db.expire_all()
    assert db.query(TransactionDB).filter_by(id=row.id).one().type == "credit"


def test_update_rejects_an_unknown_type(client, user, auth_headers, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    response = _update(client, auth_headers, row.id, category_id=category_ids["Alimentação"], type="refund")

    assert response.status_code == 422


def test_update_cannot_change_another_users_transaction(
    client, db, user, other_user, headers_for, make_transaction, category_ids
):
    theirs = make_transaction(other_user, category_ids["Alimentação"], label="Theirs", value=1000)

    response = _update(client, headers_for(user), theirs.id, category_id=category_ids["Alimentação"])

    assert response.status_code == 404
    db.expire_all()
    untouched = db.query(TransactionDB).filter_by(id=theirs.id).one()
    assert (untouched.label, untouched.value) == ("Theirs", 1000)


def test_update_of_an_unknown_id_is_not_found(client, auth_headers, category_ids):
    response = _update(client, auth_headers, 999999, category_id=category_ids["Alimentação"])

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_update_with_an_unknown_category_is_not_found_and_changes_nothing(
    client, db, user, auth_headers, make_transaction, category_ids
):
    row = make_transaction(user, category_ids["Alimentação"], label="Velho", value=1000)

    response = _update(client, auth_headers, row.id, category_id=999999)

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"
    db.expire_all()
    assert db.query(TransactionDB).filter_by(id=row.id).one().label == "Velho"


@pytest.mark.parametrize(
    "fields",
    [{"value": 0}, {"value": -5}, {"value": 2147483648}, {"label": ""}, {"label": "x" * 101}],
)
def test_update_rejects_invalid_values(client, db, user, auth_headers, make_transaction, category_ids, fields):
    row = make_transaction(user, category_ids["Alimentação"], label="Velho", value=1000)

    response = _update(client, auth_headers, row.id, category_id=category_ids["Alimentação"], **fields)

    assert response.status_code == 422
    db.expire_all()
    saved = db.query(TransactionDB).filter_by(id=row.id).one()
    assert (saved.label, saved.value) == ("Velho", 1000)


def test_update_requires_authentication(client, user, make_transaction, category_ids):
    row = make_transaction(user, category_ids["Alimentação"])

    response = client.put(f"/transactions/{row.id}", json={"label": "x", "value": 1, "category_id": 1})

    assert response.status_code == 401


# --- export -------------------------------------------------------------------


def _export(client, headers, file_format=None):
    params = {} if file_format is None else {"format": file_format}
    return client.get("/transactions/export", params=params, headers=headers)


def _csv_rows(response):
    return response.content.decode("utf-8-sig").split("\r\n")[:-1]


def test_export_csv_has_the_documented_columns_and_brazilian_formatting(
    client, user, auth_headers, make_transaction, category_ids
):
    make_transaction(user, category_ids["Alimentação"], label="Almoço", value=123456, when=datetime(2026, 3, 15, 12, 0))
    make_transaction(
        user, category_ids["Transporte"], label="Salário", value=5, when=datetime(2026, 3, 1), type="credit"
    )

    response = _export(client, auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert _csv_rows(response) == [
        "Data;Descrição;Categoria;Valor;Tipo",
        "15/03/2026;Almoço;Alimentação;1.234,56;Débito",
        "01/03/2026;Salário;Transporte;0,05;Crédito",
    ]


def test_export_is_offered_as_a_download_with_a_dated_file_name(client, auth_headers):
    response = _export(client, auth_headers)

    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="transacoes-')
    assert disposition.endswith('.csv"')


def test_export_defaults_to_csv(client, auth_headers):
    assert _export(client, auth_headers).headers["content-type"].startswith("text/csv")


def test_export_xlsx_has_real_dates_and_numbers(client, user, auth_headers, make_transaction, category_ids):
    import io

    from openpyxl import load_workbook

    make_transaction(user, category_ids["Alimentação"], label="Almoço", value=123456, when=datetime(2026, 3, 15, 12, 0))

    response = _export(client, auth_headers, "xlsx")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.xlsx"')
    sheet = load_workbook(io.BytesIO(response.content)).active
    assert [c.value for c in sheet[1]] == ["Data", "Descrição", "Categoria", "Valor", "Tipo"]
    date_cell, label, category, amount, kind = sheet[2]
    assert (date_cell.value, label.value, category.value, amount.value, kind.value) == (
        datetime(2026, 3, 15, 12, 0),
        "Almoço",
        "Alimentação",
        1234.56,
        "Débito",
    )


def test_export_only_contains_the_callers_transactions(
    client, user, other_user, auth_headers, make_transaction, category_ids
):
    food = category_ids["Alimentação"]
    make_transaction(user, food, label="Meu")
    make_transaction(other_user, food, label="Segredo do outro")

    text = _export(client, auth_headers).content.decode("utf-8-sig")

    assert "Meu" in text
    assert "Segredo do outro" not in text


def test_export_has_every_transaction_not_just_one_page(client, db, user, auth_headers, category_ids):
    db.add_all(
        TransactionDB(
            user_id=user.id, label=f"t{i}", value=100, transactioned_at=datetime(2026, 1, 1), category_id=None
        )
        for i in range(250)
    )
    db.commit()

    assert len(_csv_rows(_export(client, auth_headers))) == 1 + 250


def test_export_lists_the_newest_first(client, user, auth_headers, make_transaction, category_ids):
    food = category_ids["Alimentação"]
    make_transaction(user, food, label="velha", when=datetime(2026, 1, 1))
    make_transaction(user, food, label="nova", when=datetime(2026, 3, 1))

    labels = [row.split(";")[1] for row in _csv_rows(_export(client, auth_headers))[1:]]

    assert labels == ["nova", "velha"]


def test_export_without_transactions_is_just_the_header(client, auth_headers):
    assert _csv_rows(_export(client, auth_headers)) == ["Data;Descrição;Categoria;Valor;Tipo"]


def test_export_shows_a_missing_category_as_empty(client, user, auth_headers, make_transaction):
    make_transaction(user, None, label="Sem categoria", when=datetime(2026, 3, 15))

    assert _csv_rows(_export(client, auth_headers))[1] == "15/03/2026;Sem categoria;;25,00;Débito"


def test_export_does_not_let_a_description_run_as_a_formula(client, user, auth_headers, make_transaction, category_ids):
    make_transaction(user, category_ids["Alimentação"], label='=HYPERLINK("http://evil")')

    assert "'=HYPERLINK" in _export(client, auth_headers).content.decode("utf-8-sig")


@pytest.mark.parametrize("file_format", ["pdf", "XLSX", ""])
def test_export_rejects_an_unknown_format(client, auth_headers, file_format):
    assert _export(client, auth_headers, file_format).status_code == 422


def test_export_requires_authentication(client):
    assert client.get("/transactions/export").status_code == 401


# --- error codes (TKT-28) ------------------------------------------------


def test_deleting_an_unknown_transaction_is_not_found(client, auth_headers):
    assert client.delete("/transactions/999999", headers=auth_headers).status_code == 404


def test_deleting_another_users_transaction_is_not_found(
    client, user, other_user, headers_for, make_transaction, category_ids
):
    theirs = make_transaction(other_user, category_ids["Alimentação"])

    assert client.delete(f"/transactions/{theirs.id}", headers=headers_for(user)).status_code == 404


def test_creating_with_an_unknown_category_is_a_client_error(db, user, auth_headers):
    from fastapi.testclient import TestClient

    from api.app import app

    # raise_server_exceptions=False: we want to see the status code a real client would get
    response = TestClient(app, raise_server_exceptions=False).post(
        "/transactions/create", json={"label": "x", "value": 100, "category_id": 999999}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


# --- known bugs (TKT-26) ---------------------------------------------------


@pytest.mark.skip(reason="TKT-26: a date grouping without a date crashes with a 500 instead of a client error")
@pytest.mark.parametrize("path", ["/transactions/", "/transactions/summed-by-category"])
def test_grouping_without_a_date_is_a_client_error(client, auth_headers, path):
    response = client.post(path, json={"organized_by": "day"}, headers=auth_headers)

    assert response.status_code == 422

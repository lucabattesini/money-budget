"""Importing transactions in steps: upload (the whole file is checked), settle the categories, confirm.

Like the export tests, the background work is held back by the `queue` fixture and run on demand.
"""

import io
from datetime import date, datetime, timedelta

import pytest
from openpyxl import Workbook

from api.controllers import imports_controller
from api.routers import imports_router
from schemas.tables import Categories, Families, ImportJobDB, TransactionDB

HEADER = "Data;Descrição;Categoria;Valor;Tipo"
GOOD_ROW = "15/03/2026;Almoço;Restaurantes e Bares;1.234,56;Débito"


@pytest.fixture
def queue(monkeypatch):
    pending = []
    monkeypatch.setattr(imports_router, "run_import_job", pending.append)

    class Queue:
        @staticmethod
        def run():
            while pending:
                imports_controller.run_import_job(pending.pop(0))

    return Queue()


def _csv(*lines, header=HEADER):
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


def _xlsx(rows):
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _upload(client, headers, content, name="transacoes.csv"):
    return client.post("/imports", files={"file": (name, content, "application/octet-stream")}, headers=headers)


def _stage(client, headers, *lines, **kwargs):
    response = _upload(client, headers, _csv(*lines, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _choose(client, headers, job_id, mapping):
    return client.put(f"/imports/{job_id}/categories", json={"mapping": mapping}, headers=headers)


def _start(client, headers, job_id):
    return client.post(f"/imports/{job_id}/start", headers=headers)


def _import(client, queue, headers, *lines, mapping=None):
    """All three steps; returns the finished job."""
    job = _stage(client, headers, *lines)
    if mapping:
        assert _choose(client, headers, job["id"], mapping).status_code == 200
    assert _start(client, headers, job["id"]).status_code == 202
    queue.run()
    return client.get(f"/imports/{job['id']}", headers=headers).json()["data"]


def _problems(response):
    return [(p["row"], p["message"]) for p in response.json()["problems"]]


def _saved(db, user):
    return db.query(TransactionDB).filter_by(family_id=user.family_id).order_by(TransactionDB.id).all()


# --- step 1: the file is checked before anything is kept -----------------------------------------------------------


def test_a_good_file_is_staged_and_nothing_is_saved_yet(client, db, user, auth_headers):
    job = _stage(client, auth_headers, GOOD_ROW, "01/03/2026;Salário;Aluguel;5,00;Crédito")

    assert job["status"] == "staged"
    assert (job["filename"], job["total_rows"], job["to_import"], job["skipped_count"]) == ("transacoes.csv", 2, 2, 0)
    assert job["unknown_categories"] == []
    assert _saved(db, user) == []


def test_one_wrong_row_rejects_the_whole_file_and_every_problem_is_listed(client, db, user, auth_headers):
    response = _upload(
        client,
        auth_headers,
        _csv(
            GOOD_ROW,
            "31/02/2026;Almoço;Aluguel;10,00;Débito",  # row 3: not a day
            "15/03/2026;;Aluguel;10,00;Débito",  # row 4: no description
            "15/03/2026;Padaria;Aluguel;0;Débito",  # row 5: amount not above zero
            "15/03/2026;Padaria;Aluguel;dez;Débito",  # row 6: not a number
            "15/03/2026;Padaria;Aluguel;10,00;Pix",  # row 7: unknown type
            "15/03/2026;Padaria;;10,00;Débito",  # row 8: no category
        ),
    )

    assert response.status_code == 422
    body = response.json()
    assert "Nada foi importado" in body["detail"]
    assert [row for row, _ in _problems(response)] == [3, 4, 5, 6, 7, 8]
    assert body["problems_total"] == 6
    assert db.query(ImportJobDB).count() == 0
    assert _saved(db, user) == []


def test_a_row_with_several_mistakes_lists_each_one(client, auth_headers):
    response = _upload(client, auth_headers, _csv("amanhã;;Aluguel;-3;Pix"))

    assert [row for row, _ in _problems(response)] == [2, 2, 2, 2]


def test_a_date_in_the_future_is_a_problem(client, auth_headers):
    tomorrow = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")

    response = _upload(client, auth_headers, _csv(f"{tomorrow};Almoço;Aluguel;10,00;Débito"))

    assert _problems(response) == [(2, "A data não pode ser no futuro.")]


def test_today_is_fine(client, auth_headers):
    today = date.today().strftime("%d/%m/%Y")

    assert _upload(client, auth_headers, _csv(f"{today};Almoço;Aluguel;10,00;Débito")).status_code == 201


@pytest.mark.parametrize("amount", ["0", "0,00", "-5,00", "abc", "1,234", "1.5.5", ""])
def test_amounts_that_are_not_above_zero_or_not_numbers_are_problems(client, auth_headers, amount):
    response = _upload(client, auth_headers, _csv(f"15/03/2026;Almoço;Aluguel;{amount};Débito"))

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]


def test_a_description_over_the_limit_is_a_problem(client, auth_headers):
    response = _upload(client, auth_headers, _csv(f"15/03/2026;{'a' * 101};Aluguel;1,00;Débito"))

    assert "101 caracteres" in _problems(response)[0][1]
    assert _upload(client, auth_headers, _csv(f"15/03/2026;{'a' * 100};Aluguel;1,00;Débito")).status_code == 201


def test_the_type_column_is_optional_and_defaults_to_debit(client, db, user, auth_headers, queue):
    staged = _upload(client, auth_headers, _csv("15/03/2026;Almoço;Aluguel;10,00", header="Data;Descrição;Categoria;Valor"))
    assert staged.status_code == 201
    assert _start(client, auth_headers, staged.json()["data"]["id"]).status_code == 202
    queue.run()

    assert [t.type for t in _saved(db, user)] == ["debit"]


def test_columns_may_come_in_any_order_and_extra_columns_are_ignored(client, db, user, auth_headers, queue):
    staged = _upload(
        client,
        auth_headers,
        _csv("10,00;Aluguel;ignorar;Almoço;15/03/2026", header="valor;CATEGORIA;Banco;descrição;data"),
    )
    assert staged.status_code == 201
    _start(client, auth_headers, staged.json()["data"]["id"])
    queue.run()

    saved = _saved(db, user)
    assert [(t.label, t.value) for t in saved] == [("Almoço", 1000)]


def test_missing_columns_are_named(client, auth_headers):
    response = _upload(client, auth_headers, _csv("15/03/2026;Almoço", header="Data;Descrição"))

    assert response.status_code == 422
    assert "Categoria" in response.json()["detail"] and "Valor" in response.json()["detail"]


@pytest.mark.parametrize(
    "name, content, message",
    [
        ("dados.pdf", b"%PDF", ".xlsx"),
        ("dados", b"x", ".xlsx"),
        ("dados.csv", b"", "vazio"),
        ("dados.csv", HEADER.encode() + b"\n", "nenhuma transação"),
        ("dados.csv", "Data;Descrição\n".encode("latin-1"), "UTF-8"),
        ("dados.xlsx", b"not a zip", "Excel"),
    ],
)
def test_a_file_that_cannot_be_used_gets_a_clear_message(client, db, auth_headers, name, content, message):
    response = _upload(client, auth_headers, content, name)

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert db.query(ImportJobDB).count() == 0


def test_a_file_over_the_size_limit_is_refused(client, auth_headers, monkeypatch):
    monkeypatch.setattr(imports_router, "MAX_FILE_BYTES", 10)
    monkeypatch.setattr(imports_controller, "MAX_FILE_BYTES", 10)

    response = _upload(client, auth_headers, _csv(GOOD_ROW))

    assert response.status_code == 422
    assert "grande demais" in response.json()["detail"]


def test_a_file_with_too_many_rows_is_refused(client, auth_headers, monkeypatch):
    from api.gateways.documents import csv_gateway

    monkeypatch.setattr(csv_gateway, "MAX_ROWS", 2)

    response = _upload(client, auth_headers, _csv(GOOD_ROW, GOOD_ROW, GOOD_ROW))

    assert response.status_code == 422
    assert "linhas demais" in response.json()["detail"]


def test_uploading_needs_a_login(client):
    assert _upload(client, {}, _csv(GOOD_ROW)).status_code in (401, 403)


@pytest.mark.parametrize("delimiter", [";", ","])
def test_csv_with_either_separator_is_imported(client, db, user, auth_headers, queue, delimiter):
    text = f'Data{delimiter}Descrição{delimiter}Categoria{delimiter}Valor\n15/03/2026{delimiter}Almoço{delimiter}Aluguel{delimiter}"1.234,56"\n'
    staged = _upload(client, auth_headers, text.encode("utf-8"))
    assert staged.status_code == 201
    _start(client, auth_headers, staged.json()["data"]["id"])
    queue.run()

    assert [(t.label, t.value) for t in _saved(db, user)] == [("Almoço", 123456)]


def test_excel_with_real_date_and_number_cells_is_imported(client, db, user, auth_headers, queue):
    content = _xlsx(
        [
            ["Data", "Descrição", "Categoria", "Valor", "Tipo"],
            [datetime(2026, 3, 15), "Almoço", "Aluguel", 1234.56, "Débito"],
            ["16/03/2026", "Salário", "Aluguel", "10,50", "Crédito"],
            [datetime(2026, 3, 17), 123, "Aluguel", 7, None],
        ]
    )
    staged = _upload(client, auth_headers, content, "planilha.xlsx")
    assert staged.status_code == 201, staged.text
    _start(client, auth_headers, staged.json()["data"]["id"])
    queue.run()

    assert [(t.transactioned_at.date(), t.label, t.value, t.type) for t in _saved(db, user)] == [
        (date(2026, 3, 15), "Almoço", 123456, "debit"),
        (date(2026, 3, 16), "Salário", 1050, "credit"),
        (date(2026, 3, 17), "123", 700, "debit"),
    ]


def test_excel_dates_in_the_future_and_bad_numbers_are_problems(client, auth_headers):
    content = _xlsx(
        [
            ["Data", "Descrição", "Categoria", "Valor"],
            [datetime.now() + timedelta(days=3), "Almoço", "Aluguel", 5],
            [datetime(2026, 3, 15), "Almoço", "Aluguel", 5.123],
            [datetime(2026, 3, 15), "Almoço", "Aluguel", -1],
        ]
    )

    response = _upload(client, auth_headers, content, "planilha.xlsx")

    assert [row for row, _ in _problems(response)] == [2, 3, 4]


# --- step 2: categories ---------------------------------------------------------------------------------------------


def test_a_category_the_family_does_not_have_is_not_an_error_but_is_listed(client, db, user, auth_headers):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito", "16/03/2026;Petisco;pets;5,00;Débito", GOOD_ROW)

    assert job["unknown_categories"] == [{"name": "Pets", "rows": 2}]  # spelled differently, still one category
    assert db.query(ImportJobDB).one().status == "staged"


def test_the_import_cannot_start_while_a_category_is_unsettled(client, db, user, auth_headers, queue):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")

    response = _start(client, auth_headers, job["id"])

    assert response.status_code == 409
    assert "categoria" in response.json()["detail"]
    assert db.query(ImportJobDB).one().status == "staged"


def test_an_unknown_category_can_be_mapped_to_an_existing_one(client, db, user, auth_headers, category_ids, queue):
    job = _import(
        client, queue, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito", mapping={"Pets": category_ids["Supermercado"]}
    )

    assert job["status"] == "done"
    assert [t.category_id for t in _saved(db, user)] == [category_ids["Supermercado"]]


def test_choosing_shows_the_remaining_categories(client, auth_headers, category_ids):
    job = _stage(client, auth_headers, "15/03/2026;a;Pets;1,00", "15/03/2026;b;Viagens;1,00")

    after = _choose(client, auth_headers, job["id"], {"pets": category_ids["Aluguel"]}).json()["data"]

    assert [c["name"] for c in after["unknown_categories"]] == ["Viagens"]


def test_creating_the_category_in_the_family_settles_it_by_itself(client, db, user, auth_headers, queue):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")
    created = client.post("/categories", json={"name": "🐶 Pets"}, headers=auth_headers)
    assert created.status_code in (200, 201), created.text

    after = client.get(f"/imports/{job['id']}", headers=auth_headers).json()["data"]
    assert after["unknown_categories"] == []

    _start(client, auth_headers, job["id"])
    queue.run()
    assert [t.category_id for t in _saved(db, user)] == [created.json()["data"]["id"]]


def test_a_family_category_wins_over_a_default_one_with_the_same_name(client, db, user, auth_headers, queue):
    own = Categories(name="Aluguel", family_id=user.family_id)
    db.add(own)
    db.commit()

    _import(client, queue, auth_headers, "15/03/2026;Casa;Aluguel;1,00;Débito")

    assert [t.category_id for t in _saved(db, user)] == [own.id]


def test_a_category_that_does_not_exist_cannot_be_chosen(client, auth_headers):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")

    assert _choose(client, auth_headers, job["id"], {"Pets": 999999}).status_code == 422


def test_another_familys_category_cannot_be_chosen(client, db, user, other_user, auth_headers):
    foreign = Categories(name="Segredo", family_id=other_user.family_id)
    db.add(foreign)
    db.commit()
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")

    assert _choose(client, auth_headers, job["id"], {"Pets": foreign.id}).status_code == 422


def test_a_name_that_is_not_in_the_file_cannot_be_mapped(client, auth_headers, category_ids):
    job = _stage(client, auth_headers, GOOD_ROW)

    assert _choose(client, auth_headers, job["id"], {"Pets": category_ids["Aluguel"]}).status_code == 422


def test_a_category_deleted_after_choosing_makes_the_import_fail_and_save_nothing(
    client, db, user, auth_headers, queue
):
    own = Categories(name="Temporária", family_id=user.family_id)
    db.add(own)
    db.commit()
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito", GOOD_ROW)
    _choose(client, auth_headers, job["id"], {"Pets": own.id})
    _start(client, auth_headers, job["id"])
    db.delete(own)
    db.commit()

    queue.run()

    after = client.get(f"/imports/{job['id']}", headers=auth_headers).json()["data"]
    assert after["status"] == "failed" and "Comece de novo" in after["error"]
    assert _saved(db, user) == []


# --- step 3: the import ---------------------------------------------------------------------------------------------


def test_starting_answers_accepted_and_the_work_waits_for_the_background(client, db, user, auth_headers, queue):
    job = _stage(client, auth_headers, GOOD_ROW)

    response = _start(client, auth_headers, job["id"])

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "queued"
    assert _saved(db, user) == []

    queue.run()
    assert len(_saved(db, user)) == 1


def test_imported_transactions_belong_to_the_family_and_were_created_by_the_person(
    client, db, user, other_user, auth_headers, queue
):
    job = _import(client, queue, auth_headers, GOOD_ROW, "01/03/2026;Salário;Aluguel;5,00;Crédito")

    assert (job["status"], job["total_rows"], job["imported_count"], job["skipped_count"]) == ("done", 2, 2, 0)
    saved = _saved(db, user)
    assert [(t.label, t.value, t.type, t.transactioned_at.date()) for t in saved] == [
        ("Almoço", 123456, "debit", date(2026, 3, 15)),
        ("Salário", 500, "credit", date(2026, 3, 1)),
    ]
    assert {t.user_id for t in saved} == {user.id}
    assert _saved(db, other_user) == []


def test_the_finished_job_keeps_no_rows(client, db, user, auth_headers, queue):
    _import(client, queue, auth_headers, GOOD_ROW)

    assert db.query(ImportJobDB).one().rows is None


def test_rows_the_family_already_has_are_skipped_and_listed(
    client, db, user, auth_headers, make_transaction, category_ids, queue
):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Almoço", 123456, datetime(2026, 3, 15, 20, 45))

    job = _import(client, queue, auth_headers, GOOD_ROW, "16/03/2026;Jantar;Restaurantes e Bares;10,00;Débito")

    assert (job["imported_count"], job["skipped_count"]) == (1, 1)
    assert [(s["row"], s["label"]) for s in job["skipped"]] == [(2, "Almoço")]
    assert len(_saved(db, user)) == 2


@pytest.mark.parametrize(
    "line",
    [
        "16/03/2026;Almoço;Restaurantes e Bares;1.234,56;Débito",  # another day
        "15/03/2026;Almoços;Restaurantes e Bares;1.234,56;Débito",  # another description
        "15/03/2026;Almoço;Restaurantes e Bares;1.234,57;Débito",  # another amount
        "15/03/2026;Almoço;Aluguel;1.234,56;Débito",  # another category
        "15/03/2026;Almoço;Restaurantes e Bares;1.234,56;Crédito",  # another type
    ],
)
def test_a_row_that_differs_in_any_way_is_not_a_duplicate(
    client, db, user, auth_headers, make_transaction, category_ids, queue, line
):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Almoço", 123456, datetime(2026, 3, 15, 8, 0))

    job = _import(client, queue, auth_headers, line)

    assert (job["imported_count"], job["skipped_count"]) == (1, 0)


def test_another_familys_transactions_do_not_make_a_row_a_duplicate(
    client, db, user, other_user, auth_headers, make_transaction, category_ids, queue
):
    make_transaction(other_user, category_ids["Restaurantes e Bares"], "Almoço", 123456, datetime(2026, 3, 15, 8, 0))

    job = _import(client, queue, auth_headers, GOOD_ROW)

    assert job["imported_count"] == 1


def test_importing_the_same_file_twice_does_not_duplicate_anything(client, db, user, auth_headers, queue):
    lines = (GOOD_ROW, "01/03/2026;Salário;Aluguel;5,00;Crédito")
    _import(client, queue, auth_headers, *lines)

    again = _import(client, queue, auth_headers, *lines)

    assert (again["imported_count"], again["skipped_count"]) == (0, 2)
    assert len(_saved(db, user)) == 2


def test_the_summary_before_starting_already_shows_the_duplicates(
    client, db, user, auth_headers, make_transaction, category_ids
):
    make_transaction(user, category_ids["Restaurantes e Bares"], "Almoço", 123456, datetime(2026, 3, 15, 8, 0))

    job = _stage(client, auth_headers, GOOD_ROW, "16/03/2026;Jantar;Aluguel;1,00")

    assert (job["to_import"], job["skipped_count"]) == (1, 1)
    assert job["skipped"][0]["label"] == "Almoço"


def test_identical_rows_inside_the_file_are_both_imported(client, db, user, auth_headers, queue):
    job = _import(client, queue, auth_headers, GOOD_ROW, GOOD_ROW)

    assert (job["imported_count"], job["skipped_count"]) == (2, 0)
    assert len(_saved(db, user)) == 2


def test_if_saving_fails_nothing_is_saved_and_the_person_gets_a_generic_message(
    client, db, user, auth_headers, queue, monkeypatch
):
    def explode(*args, **kwargs):
        raise RuntimeError("secret database detail")

    job = _stage(client, auth_headers, GOOD_ROW)
    _start(client, auth_headers, job["id"])
    monkeypatch.setattr(imports_controller, "add_transactions", explode)

    queue.run()

    after = client.get(f"/imports/{job['id']}", headers=auth_headers).json()["data"]
    assert after["status"] == "failed"
    assert after["error"] == imports_controller.FAILED_MESSAGE
    assert "secret" not in str(after)
    assert _saved(db, user) == []


def test_a_file_made_by_the_export_can_be_imported_back(client, db, user, auth_headers, category_ids, queue):
    from api.services.export_service import export_transactions
    from schemas.tables_schemas import TransactionOut
    from api.repositories.transactions_repo import list_all_transactions

    for label, value, kind in [("=1+1", 123456, "debit"), ("@fulano", 5, "credit"), ("Almoço", 2500, "debit")]:
        db.add(
            TransactionDB(
                family_id=user.family_id,
                user_id=user.id,
                label=label,
                value=value,
                type=kind,
                transactioned_at=datetime(2026, 3, 15, 10, 0),
                category_id=category_ids["Aluguel"],
            )
        )
    db.commit()
    transactions = list_all_transactions(db, user.family_id)
    assert all(isinstance(t, TransactionOut) for t in transactions)
    db.query(TransactionDB).delete()  # as if it was a new account
    db.commit()

    for file_format, name in [("csv", "export.csv"), ("xlsx", "export.xlsx")]:
        document = export_transactions(transactions, file_format)
        staged = _upload(client, auth_headers, document.content, name)
        assert staged.status_code == 201, staged.text
        _start(client, auth_headers, staged.json()["data"]["id"])
        queue.run()
        saved = _saved(db, user)
        assert sorted((t.label, t.value, t.type) for t in saved) == sorted(
            (t.label, t.value, t.type) for t in transactions
        )
        db.query(TransactionDB).delete()
        db.commit()


# --- one at a time, stuck jobs, who sees what --------------------------------------------------------------------------


def test_a_second_import_is_refused_while_one_is_waiting_and_allowed_when_it_finishes(
    client, db, user, auth_headers, queue
):
    first = _stage(client, auth_headers, GOOD_ROW)
    assert _start(client, auth_headers, first["id"]).status_code == 202
    second = _upload(client, auth_headers, _csv("01/03/2026;Salário;Aluguel;5,00;Crédito"))
    assert second.status_code == 201  # uploading is fine, it is only starting that waits

    refused = _start(client, auth_headers, second.json()["data"]["id"])

    assert refused.status_code == 409
    assert "andamento" in refused.json()["detail"]

    queue.run()
    assert _start(client, auth_headers, second.json()["data"]["id"]).status_code == 202


def test_the_limit_is_per_family(client, db, user, other_user, auth_headers, headers_for, queue):
    mine = _stage(client, auth_headers, GOOD_ROW)
    theirs = _stage(client, headers_for(other_user), GOOD_ROW)

    assert _start(client, auth_headers, mine["id"]).status_code == 202
    assert _start(client, headers_for(other_user), theirs["id"]).status_code == 202


def test_a_job_stuck_in_queued_is_cancelled_and_no_longer_blocks_a_new_import(client, db, user, auth_headers, queue):
    stuck = _stage(client, auth_headers, GOOD_ROW)
    _start(client, auth_headers, stuck["id"])
    job = db.get(ImportJobDB, stuck["id"])
    job.queued_at = datetime.now() - timedelta(minutes=10)
    db.commit()

    shown = client.get(f"/imports/{stuck['id']}", headers=auth_headers).json()["data"]
    assert shown["status"] == "failed" and "cancelada" in shown["error"]

    fresh = _stage(client, auth_headers, "01/03/2026;Salário;Aluguel;5,00;Crédito")
    assert _start(client, auth_headers, fresh["id"]).status_code == 202


def test_a_new_upload_replaces_the_file_the_person_had_not_finished(client, db, user, auth_headers):
    first = _stage(client, auth_headers, GOOD_ROW)
    second = _stage(client, auth_headers, "01/03/2026;Salário;Aluguel;5,00;Crédito")

    assert client.get(f"/imports/{first['id']}", headers=auth_headers).status_code == 404
    assert client.get(f"/imports/{second['id']}", headers=auth_headers).status_code == 200


def test_giving_up_throws_the_staged_file_away(client, db, user, auth_headers):
    job = _stage(client, auth_headers, GOOD_ROW)

    assert client.delete(f"/imports/{job['id']}", headers=auth_headers).status_code == 204
    assert db.query(ImportJobDB).count() == 0


def test_a_started_import_cannot_be_given_up_or_started_again_or_changed(client, auth_headers, queue, category_ids):
    job = _stage(client, auth_headers, GOOD_ROW)
    _start(client, auth_headers, job["id"])

    assert client.delete(f"/imports/{job['id']}", headers=auth_headers).status_code == 409
    assert _start(client, auth_headers, job["id"]).status_code == 409
    assert _choose(client, auth_headers, job["id"], {}).status_code == 409


def test_old_jobs_are_deleted_when_someone_uploads(client, db, user, other_user, auth_headers):
    old = ImportJobDB(
        family_id=other_user.family_id,
        requested_by=other_user.id,
        status="done",
        created_at=datetime.now() - timedelta(days=2),
    )
    db.add(old)
    db.commit()
    old_id = old.id

    _stage(client, auth_headers, GOOD_ROW)

    assert db.query(ImportJobDB).filter_by(id=old_id).count() == 0


def test_an_expired_job_is_not_found(client, db, user, auth_headers):
    job = _stage(client, auth_headers, GOOD_ROW)
    db.get(ImportJobDB, job["id"]).created_at = datetime.now() - timedelta(days=2)
    db.commit()

    assert client.get(f"/imports/{job['id']}", headers=auth_headers).status_code == 404


def test_nobody_else_can_see_or_use_a_job_not_even_in_the_same_family(
    client, db, user, make_user, other_user, auth_headers, headers_for, category_ids
):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")
    relative = make_user("Relative", family=db.get(Families, user.family_id))
    strangers = [headers_for(other_user), headers_for(relative)]

    for headers in strangers:
        assert client.get(f"/imports/{job['id']}", headers=headers).status_code == 404
        assert _choose(client, headers, job["id"], {"Pets": category_ids["Aluguel"]}).status_code == 404
        assert _start(client, headers, job["id"]).status_code == 404
        assert client.delete(f"/imports/{job['id']}", headers=headers).status_code == 404
    assert db.query(ImportJobDB).one().status == "staged"


def test_an_unknown_job_is_not_found(client, auth_headers):
    assert client.get("/imports/999999", headers=auth_headers).status_code == 404

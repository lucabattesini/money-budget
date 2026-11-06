"""Importing transactions in steps: upload (the whole file is checked), settle the categories, confirm.

Like the export tests, the background work is held back by the `queue` fixture and run on demand.
"""

import io
from datetime import date, datetime, timedelta

import pytest
from openpyxl import Workbook

from api.controllers import imports_controller
from api.routers import imports_router
from api.utils.clock import family_today
from schemas.tables import Categories, CategoryGroups, Families, ImportJobDB, Merchants, TransactionDB
from tests.conftest import MISSING_ID

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


def _match(client, headers, job_id, mapping, date_order=None, **formats):
    """`formats` may hold amount_style and sign, as the dialog sends them."""
    body = {"mapping": mapping, **formats}
    if date_order is not None:
        body["date_order"] = date_order
    return client.put(f"/imports/{job_id}/columns", json=body, headers=headers)


def _check(client, headers, content, name="transacoes.csv"):
    """Upload, then match the columns the way the page suggests. Returns the answer of the matching, where every row
    of the file is checked."""
    uploaded = _upload(client, headers, content, name)
    assert uploaded.status_code == 201, uploaded.text
    data = uploaded.json()["data"]
    return _match(client, headers, data["id"], data["suggested_map"])


def _stage_file(client, headers, content, name="transacoes.csv"):
    response = _check(client, headers, content, name)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _stage(client, headers, *lines, **kwargs):
    """Upload and match the columns by name; the file is checked and waits for the categories."""
    return _stage_file(client, headers, _csv(*lines, **kwargs))


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
    return (
        db.query(TransactionDB)
        .filter_by(family_id=user.family_id)
        .order_by(TransactionDB.transactioned_at, TransactionDB.label, TransactionDB.value)
        .all()
    )


# --- step 1: the file is checked before anything is kept -----------------------------------------------------------


def test_a_good_file_is_staged_and_nothing_is_saved_yet(client, db, user, auth_headers):
    job = _stage(client, auth_headers, GOOD_ROW, "01/03/2026;Salário;Aluguel;5,00;Crédito")

    assert job["status"] == "staged"
    assert (job["filename"], job["total_rows"], job["to_import"], job["skipped_count"]) == ("transacoes.csv", 2, 2, 0)
    assert job["unknown_categories"] == []
    assert _saved(db, user) == []


def test_one_wrong_row_rejects_the_whole_file_and_every_problem_is_listed(client, db, user, auth_headers):
    response = _check(
        client,
        auth_headers,
        _csv(
            GOOD_ROW,
            "31/02/2026;Almoço;Aluguel;10,00;Débito",  # row 3: not a day
            "15/03/2026;;Aluguel;10,00;Débito",  # row 4: no description
            "15/03/2026;Padaria;Aluguel;-1,00;Débito",  # row 5: negative amount
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
    assert (
        db.query(ImportJobDB).one().rows is None
    )  # the file waits, unchecked, for another matching; no rows were kept
    assert _saved(db, user) == []


def test_a_row_with_several_mistakes_lists_each_one(client, auth_headers):
    response = _check(client, auth_headers, _csv("amanhã;;Aluguel;-3;Pix"))

    assert [row for row, _ in _problems(response)] == [2, 2, 2, 2]


def test_a_date_in_the_future_is_a_problem(client, auth_headers):
    tomorrow = (family_today("America/Sao_Paulo") + timedelta(days=1)).strftime("%d/%m/%Y")

    response = _check(client, auth_headers, _csv(f"{tomorrow};Almoço;Aluguel;10,00;Débito"))

    assert _problems(response) == [(2, "A data não pode ser no futuro.")]


def test_a_date_is_in_the_future_by_the_familys_calendar_not_the_servers(client, auth_headers, set_clock):
    set_clock(datetime(2026, 4, 1, 1, 30))  # 1 April in UTC, but 31 March in Brasília

    response = _check(client, auth_headers, _csv("01/04/2026;Almoço;Aluguel;10,00;Débito"))
    assert _problems(response) == [(2, "A data não pode ser no futuro.")]
    assert _check(client, auth_headers, _csv("31/03/2026;Almoço;Aluguel;10,00;Débito")).status_code == 200


def test_today_is_fine(client, auth_headers):
    today = family_today("America/Sao_Paulo").strftime("%d/%m/%Y")

    assert _check(client, auth_headers, _csv(f"{today};Almoço;Aluguel;10,00;Débito")).status_code == 200


@pytest.mark.parametrize("amount", ["-5,00", "abc", "1.5.5", ""])
def test_amounts_that_are_negative_or_not_numbers_are_problems(client, auth_headers, amount):
    response = _check(client, auth_headers, _csv(f"15/03/2026;Almoço;Aluguel;{amount};Débito"))

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]


def test_a_description_over_the_limit_is_a_problem(client, auth_headers):
    response = _check(client, auth_headers, _csv(f"15/03/2026;{'a' * 101};Aluguel;1,00;Débito"))

    assert "101 caracteres" in _problems(response)[0][1]
    assert _check(client, auth_headers, _csv(f"15/03/2026;{'a' * 100};Aluguel;1,00;Débito")).status_code == 200


def test_the_type_column_is_optional_and_defaults_to_debit(client, db, user, auth_headers, queue):
    job = _stage(client, auth_headers, "15/03/2026;Almoço;Aluguel;10,00", header="Data;Descrição;Categoria;Valor")
    assert _start(client, auth_headers, job["id"]).status_code == 202
    queue.run()

    assert [t.type for t in _saved(db, user)] == ["debit"]


def test_columns_may_come_in_any_order_and_extra_columns_are_ignored(client, db, user, auth_headers, queue):
    job = _stage(
        client, auth_headers, "10,00;Aluguel;ignorar;Almoço;15/03/2026", header="valor;CATEGORIA;Banco;descrição;data"
    )
    _start(client, auth_headers, job["id"])
    queue.run()

    saved = _saved(db, user)
    assert [(t.label, t.value) for t in saved] == [("Almoço", 1000)]


# --- step 2: matching the columns ------------------------------------------------------------------------------------

OTHER_HEADER = "Quando;O que;Tipo de gasto;Quanto"
OTHER_MAPPING = {"Data": 0, "Descrição": 1, "Categoria": 2, "Valor": 3, "Tipo": None}


def test_uploading_only_reads_the_file_so_even_a_file_full_of_mistakes_gets_to_the_matching(client, db, auth_headers):
    response = _upload(client, auth_headers, _csv("ontem;;;abc;Pix", "amanhã;;;-1;Pix"))

    assert response.status_code == 201
    job = response.json()["data"]
    assert (job["status"], job["columns"]) == ("staged", ["Data", "Descrição", "Categoria", "Valor", "Tipo"])
    assert "unknown_categories" not in job and "to_import" not in job  # nothing is checked yet
    assert db.query(TransactionDB).count() == 0


def test_the_columns_named_like_the_fields_are_suggested_even_with_other_case_or_no_accents(client, auth_headers):
    job = _upload(client, auth_headers, _csv("1;2;3;4;5", header="valor;DESCRICAO;Banco;data;categoria")).json()["data"]

    assert job["suggested_map"] == {
        "Data": 3,
        "Descrição": 1,
        "Categoria": 4,
        "Valor": 0,
        "Tipo": None,
        "Pessoa": None,
        "Estabelecimento": None,
    }


def test_a_file_from_the_export_has_every_column_suggested(client, auth_headers):
    job = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    assert job["suggested_map"] == {
        "Data": 0,
        "Descrição": 1,
        "Categoria": 2,
        "Valor": 3,
        "Tipo": 4,
        "Pessoa": None,
        "Estabelecimento": None,
    }


def test_a_column_is_suggested_for_one_field_only(client, auth_headers):
    job = _upload(client, auth_headers, _csv("1;2", header="Data;Data")).json()["data"]

    assert job["suggested_map"]["Data"] == 0


def test_a_few_rows_are_shown_to_recognise_the_columns_by(client, auth_headers):
    lines = [f"0{n}/03/2026;Item {n};Aluguel;{n},00;Débito" for n in range(1, 8)]
    lines.insert(1, ";;;;")  # an empty row is not shown

    job = _upload(client, auth_headers, _csv(*lines)).json()["data"]

    assert len(job["sample"]) == 5
    assert job["sample"][0] == ["01/03/2026", "Item 1", "Aluguel", "1,00", "Débito"]
    assert job["sample"][1][1] == "Item 2"


def test_the_sample_of_an_excel_file_shows_dates_and_numbers_as_people_write_them(client, auth_headers):
    content = _xlsx([["Data", "Valor"], [datetime(2026, 3, 15), 12.5]])

    job = _upload(client, auth_headers, content, "planilha.xlsx").json()["data"]

    assert job["sample"] == [["15/03/2026", "12.5"]]


def test_the_person_can_say_which_column_is_which_when_the_names_do_not_match(client, db, user, auth_headers, queue):
    uploaded = _upload(client, auth_headers, _csv("15/03/2026;Almoço;Aluguel;1.234,56", header=OTHER_HEADER)).json()[
        "data"
    ]
    assert uploaded["suggested_map"] == {
        "Data": None,
        "Descrição": None,
        "Categoria": None,
        "Valor": None,
        "Tipo": None,
        "Pessoa": None,
        "Estabelecimento": None,
    }

    response = _match(client, auth_headers, uploaded["id"], OTHER_MAPPING)

    assert response.status_code == 200
    assert response.json()["data"]["column_map"] == OTHER_MAPPING
    _start(client, auth_headers, uploaded["id"])
    queue.run()
    assert [(t.label, t.value, t.type) for t in _saved(db, user)] == [("Almoço", 123456, "debit")]


def test_the_type_can_be_taken_from_a_column_the_person_picks(client, db, user, auth_headers, queue):
    uploaded = _upload(
        client, auth_headers, _csv("15/03/2026;Salário;Aluguel;5,00;Crédito", header="a;b;c;d;e")
    ).json()["data"]

    _match(client, auth_headers, uploaded["id"], {**OTHER_MAPPING, "Tipo": 4})
    _start(client, auth_headers, uploaded["id"])
    queue.run()

    assert [t.type for t in _saved(db, user)] == ["credit"]


@pytest.mark.parametrize("missing", ["Data", "Descrição", "Categoria", "Valor"])
def test_every_required_field_needs_a_column(client, auth_headers, missing):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]
    mapping = {"Data": 0, "Descrição": 1, "Categoria": 2, "Valor": 3, "Tipo": 4, missing: None}

    response = _match(client, auth_headers, uploaded["id"], mapping)

    assert response.status_code == 422
    assert missing in response.json()["detail"]


def test_a_field_left_out_altogether_counts_as_missing(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    response = _match(client, auth_headers, uploaded["id"], {"Data": 0, "Descrição": 1, "Categoria": 2})

    assert response.status_code == 422 and "Valor" in response.json()["detail"]


def test_the_same_column_can_serve_two_fields(client, db, user, auth_headers, queue):
    """One column read as both the description and the category (the file has no separate ones)."""
    uploaded = _upload(client, auth_headers, _csv("15/03/2026;Almoço;Aluguel;10,00;Débito")).json()["data"]
    same_column = {"Data": 0, "Descrição": 2, "Categoria": 2, "Valor": 3, "Tipo": 4}

    response = _match(client, auth_headers, uploaded["id"], same_column)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["unknown_categories"] == []  # "Aluguel" is a category the family has
    assert _start(client, auth_headers, uploaded["id"]).status_code == 202
    queue.run()
    assert [(t.label, t.value) for t in _saved(db, user)] == [("Aluguel", 1000)]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"Valor": 9}, "não existe"),
        ({"Valor": -1}, "não existe"),
        ({"Preço": 3}, "desconhecido"),
    ],
)
def test_a_matching_that_makes_no_sense_is_refused(client, db, auth_headers, changes, message):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    response = _match(client, auth_headers, uploaded["id"], {**OTHER_MAPPING, **changes})

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert db.get(ImportJobDB, uploaded["id"]).rows is None


def test_rows_that_do_not_fit_the_chosen_columns_are_listed_and_the_person_can_choose_again(client, db, auth_headers):
    uploaded = _upload(
        client,
        auth_headers,
        _csv("15/03/2026;Almoço;Aluguel;12,00", "16/03/2026;Jantar;Aluguel;8,00", header=OTHER_HEADER),
    ).json()["data"]
    wrong = {**OTHER_MAPPING, "Descrição": 3, "Valor": 1}  # description and amount swapped

    refused = _match(client, auth_headers, uploaded["id"], wrong)

    assert refused.status_code == 422
    assert [row for row, _ in _problems(refused)] == [2, 3]
    assert db.get(ImportJobDB, uploaded["id"]).rows is None  # nothing was kept
    assert _match(client, auth_headers, uploaded["id"], OTHER_MAPPING).status_code == 200


def test_matching_again_without_changes_leaves_the_choices_alone(client, db, user, auth_headers, category_ids):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")
    assert job["new_categories"] == [{"name": "Pets", "rows": 1, "category_id": None}]
    _choose(client, auth_headers, job["id"], {"Pets": category_ids["Aluguel"]})
    before = db.query(ImportJobDB).one().rows

    again = _match(client, auth_headers, job["id"], job["column_map"]).json()["data"]

    assert again["unknown_categories"] == []  # still settled
    assert again["new_categories"] == [{"name": "Pets", "rows": 1, "category_id": str(category_ids["Aluguel"])}]
    db.expire_all()
    assert db.query(ImportJobDB).one().rows == before


def test_matching_again_with_other_columns_keeps_the_choices_about_names_still_in_the_file(
    client, db, auth_headers, category_ids
):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")
    _choose(client, auth_headers, job["id"], {"Pets": category_ids["Aluguel"]})

    again = _match(client, auth_headers, job["id"], {**job["column_map"], "Tipo": None}, sign="negative_debit").json()[
        "data"
    ]

    assert [r["type"] for r in db.query(ImportJobDB).one().rows] == ["credit"]  # the rows really changed
    assert again["unknown_categories"] == []
    assert again["new_categories"][0]["category_id"] == str(category_ids["Aluguel"])


def test_matching_again_keeps_who_the_person_chose_for_a_name(client, db, user, auth_headers, make_user):
    partner = _partner(db, user, make_user)
    job = _stage_people(client, auth_headers, "15/03/2026;Mercado;Aluguel;10,00;Débito;Apelido")
    _choose_people(client, auth_headers, job["id"], {"Apelido": partner.id})

    same = _match(client, auth_headers, job["id"], job["column_map"]).json()["data"]
    changed = _match(
        client, auth_headers, job["id"], {**job["column_map"], "Tipo": None}, sign="negative_debit"
    ).json()["data"]

    assert same["people"] == [{"name": "Apelido", "rows": 1, "user_id": str(partner.id)}]
    assert changed["people"] == [{"name": "Apelido", "rows": 1, "user_id": str(partner.id)}]


def test_categories_and_starting_wait_for_the_columns(client, db, auth_headers, category_ids):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    assert _choose(client, auth_headers, uploaded["id"], {}).status_code == 409
    assert _start(client, auth_headers, uploaded["id"]).status_code == 409
    assert db.get(ImportJobDB, uploaded["id"]).status == "staged"


def test_the_file_is_not_kept_once_the_import_is_over(client, db, user, auth_headers, queue):
    _import(client, queue, auth_headers, GOOD_ROW)

    job = db.query(ImportJobDB).one()
    assert (job.rows, job.raw_rows) == (None, None)


# --- amounts and dates in the Brazilian and the American way ----------------------------------------------------------


def _read_back(client, queue, db, user, headers, *lines, date_order=None, header=HEADER, **formats):
    """Upload, match the columns by name, import; the transactions saved as (day, label, cents)."""
    uploaded = _upload(client, headers, _csv(*lines, header=header)).json()["data"]
    response = _match(client, headers, uploaded["id"], uploaded["suggested_map"], date_order, **formats)
    assert response.status_code == 200, response.text
    _start(client, headers, uploaded["id"])
    queue.run()
    return response.json()["data"], [(t.transactioned_at.date(), t.label, t.value) for t in _saved(db, user)]


@pytest.mark.parametrize(
    "amount, cents",
    [
        ("1.234,56", 123456),  # Brazilian
        ("1,234.56", 123456),  # American
        ("1234,56", 123456),
        ("1234.56", 123456),
        ("1,234", 123400),  # three digits after the mark are a group, never decimals
        ("1.234", 123400),
        ("12,5", 1250),
        ("12.5", 1250),
        ("R$ 1.234,56", 123456),
        ("$1,234.56", 123456),
        ("1,234,567.89", 123456789),
        ("1.234.567,89", 123456789),
    ],
)
def test_amounts_are_read_in_the_brazilian_and_the_american_way(client, db, user, auth_headers, queue, amount, cents):
    _, saved = _read_back(client, queue, db, user, auth_headers, f'15/03/2026;Almoço;Aluguel;"{amount}";Débito')

    assert saved == [(date(2026, 3, 15), "Almoço", cents)]


@pytest.mark.parametrize("amount", ["1,234.567", "1.234,567", "1,5.5", "1.2.3", "12,3456", "-1,234.56"])
def test_amounts_that_are_wrong_in_either_format_are_problems(client, auth_headers, amount):
    response = _check(client, auth_headers, _csv(f'15/03/2026;Almoço;Aluguel;"{amount}";Débito'))

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]


def test_one_file_may_mix_the_two_ways_of_writing_amounts(client, db, user, auth_headers, queue):
    _, saved = _read_back(
        client, queue, db, user, auth_headers, '15/03/2026;a;Aluguel;"1.234,56"', '16/03/2026;b;Aluguel;"1,234.56"'
    )

    assert [cents for _, _, cents in saved] == [123456, 123456]


def test_excel_cells_with_american_text_amounts_and_dates_are_read(client, db, user, auth_headers, queue):
    content = _xlsx([["Data", "Descrição", "Categoria", "Valor"], ["03/15/2026", "Almoço", "Aluguel", "1,234.56"]])
    job = _stage_file(client, auth_headers, content, "planilha.xlsx")
    _start(client, auth_headers, job["id"])
    queue.run()

    assert [(t.transactioned_at.date(), t.value) for t in _saved(db, user)] == [(date(2026, 3, 15), 123456)]


def test_a_day_above_twelve_in_the_first_place_shows_the_dates_are_day_first(client, db, user, auth_headers, queue):
    answer, saved = _read_back(
        client, queue, db, user, auth_headers, "05/03/2026;a;Aluguel;1,00", "15/03/2026;b;Aluguel;1,00"
    )

    assert answer["date_order"] == "day_first"
    assert [day for day, _, _ in saved] == [date(2026, 3, 5), date(2026, 3, 15)]  # the 5th of March, not of May


def test_a_day_above_twelve_in_the_second_place_shows_the_dates_are_month_first(client, db, user, auth_headers, queue):
    answer, saved = _read_back(
        client, queue, db, user, auth_headers, "03/05/2026;a;Aluguel;1,00", "03/15/2026;b;Aluguel;1,00"
    )

    assert answer["date_order"] == "month_first"
    assert [day for day, _, _ in saved] == [date(2026, 3, 5), date(2026, 3, 15)]  # the 5th of March, not of May


def test_dates_that_could_be_either_are_day_first_whatever_the_language_of_the_family(
    client, db, user, auth_headers, queue
):
    answer, saved = _read_back(client, queue, db, user, auth_headers, "05/03/2026;a;Aluguel;1,00")
    assert answer["date_order"] == "day_first"
    assert saved[0][0] == date(2026, 3, 5)

    db.query(TransactionDB).delete()
    db.get(Families, user.family_id).language = "en"
    db.commit()
    answer, saved = _read_back(client, queue, db, user, auth_headers, "05/03/2026;a;Aluguel;1,00")
    # The file the app itself exports is day first, in any language, so a file that cannot tell is read that way
    assert answer["date_order"] == "day_first"
    assert saved[0][0] == date(2026, 3, 5)


@pytest.mark.parametrize("order, day", [("day_first", date(2026, 3, 5)), ("month_first", date(2026, 5, 3))])
def test_the_person_can_choose_the_order_of_the_dates(client, db, user, auth_headers, queue, order, day):
    answer, saved = _read_back(client, queue, db, user, auth_headers, "05/03/2026;a;Aluguel;1,00", date_order=order)

    assert answer["date_order"] == order
    assert saved[0][0] == day


def test_a_chosen_order_that_does_not_fit_the_dates_makes_them_problems(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("15/03/2026;a;Aluguel;1,00")).json()["data"]

    response = _match(
        client, auth_headers, uploaded["id"], uploaded["suggested_map"], "month_first"
    )  # there is no month 15

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]


def test_dates_that_contradict_each_other_are_problems_for_the_rows_that_do_not_fit(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("15/03/2026;a;Aluguel;1,00", "03/15/2026;b;Aluguel;1,00")).json()[
        "data"
    ]

    response = _match(
        client, auth_headers, uploaded["id"], uploaded["suggested_map"]
    )  # the language decides: day first

    assert [row for row, _ in _problems(response)] == [3]


@pytest.mark.parametrize("order", [None, "iso"])
def test_the_year_first_date_is_a_format_of_its_own(client, db, user, auth_headers, queue, order):
    _, saved = _read_back(
        client,
        queue,
        db,
        user,
        auth_headers,
        "2026-10-13;a;Aluguel;1,00",
        "2026-03-05;b;Aluguel;1,00",
        date_order=order,
    )

    assert sorted(day for day, _, _ in saved) == [date(2026, 3, 5), date(2026, 10, 13)]


@pytest.mark.parametrize("order", ["day_first", "month_first"])
def test_a_slashed_format_that_was_chosen_does_not_take_year_first_dates(client, auth_headers, order):
    uploaded = _upload(client, auth_headers, _csv("2026-10-13;a;Aluguel;1,00")).json()["data"]

    response = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], order)

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]


def test_the_year_first_format_that_was_chosen_does_not_take_slashed_dates(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("2026-10-13;a;Aluguel;1,00", "13/10/2026;b;Aluguel;1,00")).json()[
        "data"
    ]

    response = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], "iso")

    assert [row for row, _ in _problems(response)] == [3]


def test_on_automatic_the_two_kinds_of_dates_can_share_a_file(client, db, user, auth_headers, queue):
    _, saved = _read_back(
        client, queue, db, user, auth_headers, "2026-10-13;a;Aluguel;1,00", "15/03/2026;b;Aluguel;1,00"
    )

    assert sorted(day for day, _, _ in saved) == [date(2026, 3, 15), date(2026, 10, 13)]


def test_the_answer_says_the_year_first_format_was_used(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("2026-10-13;a;Aluguel;1,00")).json()["data"]

    answer = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], "iso").json()["data"]

    assert answer["date_order"] == "iso"


def test_an_unknown_order_of_dates_is_refused(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    assert _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], "sideways").status_code == 422


def test_a_date_in_the_future_is_a_problem_in_the_american_order_too(client, auth_headers):
    future = f"03/15/{date.today().year + 1}"  # a 15 in the second place: month first

    response = _check(client, auth_headers, _csv(f"{future};Almoço;Aluguel;1,00;Débito"))

    assert response.status_code == 422
    assert _problems(response) == [(2, "A data não pode ser no futuro.")]


# --- the patterns the person chooses: how amounts are written and what their sign means ---------------------------------

NO_TYPE_HEADER = "Data;Descrição;Categoria;Valor"


@pytest.mark.parametrize(
    "style, amount, cents",
    [("br", "1.234,56", 123456), ("br", "1.234", 123400), ("us", "1,234.56", 123456), ("us", "1,234", 123400)],
)
def test_the_chosen_amount_style_is_the_one_used(client, db, user, auth_headers, queue, style, amount, cents):
    _, saved = _read_back(
        client, queue, db, user, auth_headers, f'15/03/2026;a;Aluguel;"{amount}";Débito', amount_style=style
    )

    assert saved == [(date(2026, 3, 15), "a", cents)]


@pytest.mark.parametrize(
    "style, amount",
    [("br", "1,234.56"), ("br", "1,234"), ("us", "1.234,56"), ("us", "1.234"), ("us", "12,5")],
)
def test_an_amount_in_the_other_style_is_a_problem_when_a_style_was_chosen(client, auth_headers, style, amount):
    uploaded = _upload(client, auth_headers, _csv(f'15/03/2026;a;Aluguel;"{amount}";Débito')).json()["data"]

    response = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], amount_style=style)

    assert response.status_code == 422
    assert [row for row, _ in _problems(response)] == [2]
    assert "como escolhido" in _problems(response)[0][1]


def test_the_automatic_style_accepts_both(client, db, user, auth_headers, queue):
    _, saved = _read_back(
        client,
        queue,
        db,
        user,
        auth_headers,
        '15/03/2026;a;Aluguel;"1.234,56"',
        '16/03/2026;b;Aluguel;"1,234.56"',
        header=NO_TYPE_HEADER,
        amount_style="auto",
    )

    assert [cents for _, _, cents in saved] == [123456, 123456]


def _types(db, user):
    return [(t.label, t.value, t.type) for t in _saved(db, user)]


def test_a_negative_amount_can_mean_a_debit_and_a_positive_one_a_credit(client, db, user, auth_headers, queue):
    _read_back(
        client,
        queue,
        db,
        user,
        auth_headers,
        '15/03/2026;Mercado;Aluguel;"-1.234,56"',
        "16/03/2026;Salário;Aluguel;3000,00",
        header=NO_TYPE_HEADER,
        sign="negative_debit",
    )

    assert _types(db, user) == [("Mercado", 123456, "debit"), ("Salário", 300000, "credit")]  # saved positive


def test_or_the_other_way_round_as_card_statements_do(client, db, user, auth_headers, queue):
    _read_back(
        client,
        queue,
        db,
        user,
        auth_headers,
        "15/03/2026;Mercado;Aluguel;12,50",
        "16/03/2026;Estorno;Aluguel;-3,00",
        header=NO_TYPE_HEADER,
        sign="negative_credit",
    )

    assert _types(db, user) == [("Mercado", 1250, "debit"), ("Estorno", 300, "credit")]


def test_the_sign_works_with_american_amounts(client, db, user, auth_headers, queue):
    _read_back(
        client,
        queue,
        db,
        user,
        auth_headers,
        '15/03/2026;a;Aluguel;"-1,234.56"',
        header=NO_TYPE_HEADER,
        sign="negative_debit",
        amount_style="us",
    )

    assert _types(db, user) == [("a", 123456, "debit")]


def test_the_sign_works_with_real_excel_numbers(client, db, user, auth_headers, queue):
    content = _xlsx(
        [
            ["Data", "Descrição", "Categoria", "Valor"],
            [datetime(2026, 3, 15), "a", "Aluguel", -12.5],
            [datetime(2026, 3, 16), "b", "Aluguel", 7],
        ]
    )
    uploaded = _upload(client, auth_headers, content, "extrato.xlsx").json()["data"]
    assert uploaded["suggested_sign"] == "negative_debit"
    _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], sign="negative_debit")
    _start(client, auth_headers, uploaded["id"])
    queue.run()

    assert _types(db, user) == [("a", 1250, "debit"), ("b", 700, "credit")]


@pytest.mark.parametrize("sign", ["type_column", "negative_debit", "negative_credit"])
@pytest.mark.parametrize("zero", ["0", "0,00", "0.00"])
def test_a_zero_amount_is_registered_not_refused(client, db, user, auth_headers, queue, sign, zero):
    header = HEADER if sign == "type_column" else NO_TYPE_HEADER
    line = f"15/03/2026;Brinde;Aluguel;{zero};Débito" if sign == "type_column" else f"15/03/2026;Brinde;Aluguel;{zero}"

    _read_back(client, queue, db, user, auth_headers, line, header=header, sign=sign)

    assert _types(db, user) == [("Brinde", 0, "debit")]  # a zero has no direction: it stays a debit


def test_a_zero_in_an_excel_number_cell_is_registered_too(client, db, user, auth_headers, queue):
    content = _xlsx([["Data", "Descrição", "Categoria", "Valor"], [datetime(2026, 3, 15), "Brinde", "Aluguel", 0]])
    job = _stage_file(client, auth_headers, content, "planilha.xlsx")
    _start(client, auth_headers, job["id"])
    queue.run()

    assert _types(db, user) == [("Brinde", 0, "debit")]


def test_without_the_sign_convention_a_negative_amount_is_still_a_problem(client, auth_headers):
    response = _check(client, auth_headers, _csv("15/03/2026;a;Aluguel;-5,00;Débito"))

    assert response.status_code == 422
    assert _problems(response) == [
        (2, "O valor não pode ser negativo (escolha o sinal do valor se o arquivo usa negativo para débito).")
    ]


def test_the_type_column_is_not_used_when_the_sign_says_the_direction(client, db, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("15/03/2026;a;Aluguel;-5,00;Débito")).json()["data"]
    assert uploaded["suggested_map"]["Tipo"] == 4

    response = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], sign="negative_debit")

    assert response.status_code == 422
    assert "Tipo" in response.json()["detail"]
    assert db.get(ImportJobDB, uploaded["id"]).rows is None


def test_an_unknown_amount_style_or_sign_is_refused(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv(GOOD_ROW)).json()["data"]

    assert (
        _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], amount_style="swiss").status_code == 422
    )
    assert _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"], sign="sideways").status_code == 422


@pytest.mark.parametrize(
    "header, lines, expected",
    [
        (NO_TYPE_HEADER, ["15/03/2026;a;Aluguel;-5,00"], "negative_debit"),  # nothing else says the direction
        (NO_TYPE_HEADER, ["15/03/2026;a;Aluguel;5,00"], "type_column"),  # nothing negative
        (HEADER, ["15/03/2026;a;Aluguel;-5,00;Débito"], "type_column"),  # there is a Tipo column
    ],
)
def test_the_sign_is_suggested_when_the_file_has_negative_amounts_and_no_type_column(
    client, auth_headers, header, lines, expected
):
    job = _upload(client, auth_headers, _csv(*lines, header=header)).json()["data"]

    assert job["suggested_sign"] == expected


def test_the_answer_says_how_the_file_was_read(client, auth_headers):
    uploaded = _upload(client, auth_headers, _csv("03/15/2026;a;Aluguel;-5.00", header=NO_TYPE_HEADER)).json()["data"]

    answer = _match(
        client, auth_headers, uploaded["id"], uploaded["suggested_map"], amount_style="us", sign="negative_debit"
    ).json()["data"]

    assert (answer["date_order"], answer["amount_style"], answer["sign"]) == ("month_first", "us", "negative_debit")


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
    job = _stage_file(client, auth_headers, text.encode("utf-8"))
    _start(client, auth_headers, job["id"])
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
    job = _stage_file(client, auth_headers, content, "planilha.xlsx")
    _start(client, auth_headers, job["id"])
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

    response = _check(client, auth_headers, content, "planilha.xlsx")

    assert [row for row, _ in _problems(response)] == [2, 3, 4]


# --- step 2: categories ---------------------------------------------------------------------------------------------


def test_a_category_the_family_does_not_have_is_not_an_error_but_is_listed(client, db, user, auth_headers):
    job = _stage(
        client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito", "16/03/2026;Petisco;pets;5,00;Débito", GOOD_ROW
    )

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
        client,
        queue,
        auth_headers,
        "15/03/2026;Ração;Pets;30,00;Débito",
        mapping={"Pets": category_ids["Supermercado"]},
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
    assert [str(t.category_id) for t in _saved(db, user)] == [created.json()["data"]["id"]]


def test_a_family_category_wins_over_a_default_one_with_the_same_name(client, db, user, auth_headers, queue):
    own = Categories(name="Aluguel", family_id=user.family_id)
    db.add(own)
    db.commit()

    _import(client, queue, auth_headers, "15/03/2026;Casa;Aluguel;1,00;Débito")

    assert [t.category_id for t in _saved(db, user)] == [own.id]


def test_a_category_that_does_not_exist_cannot_be_chosen(client, auth_headers):
    job = _stage(client, auth_headers, "15/03/2026;Ração;Pets;30,00;Débito")

    assert _choose(client, auth_headers, job["id"], {"Pets": MISSING_ID}).status_code == 422


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
        ("Salário", 500, "credit", date(2026, 3, 1)),
        ("Almoço", 123456, "debit", date(2026, 3, 15)),
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
    from api.repositories.transactions_repo import list_all_transactions
    from api.services.export_service import export_transactions
    from schemas.tables_schemas import TransactionOut

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
        job = _stage_file(client, auth_headers, document.content, name)
        _start(client, auth_headers, job["id"])
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
    second = _stage(
        client, auth_headers, "01/03/2026;Salário;Aluguel;5,00;Crédito"
    )  # preparing is fine, it is only starting that waits

    refused = _start(client, auth_headers, second["id"])

    assert refused.status_code == 409
    assert "andamento" in refused.json()["detail"]

    queue.run()
    assert _start(client, auth_headers, second["id"]).status_code == 202


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
        assert _match(client, headers, job["id"], job["column_map"]).status_code == 404
        assert _choose(client, headers, job["id"], {"Pets": category_ids["Aluguel"]}).status_code == 404
        assert _start(client, headers, job["id"]).status_code == 404
        assert client.delete(f"/imports/{job['id']}", headers=headers).status_code == 404
    assert db.query(ImportJobDB).one().status == "staged"


def test_an_unknown_job_is_not_found(client, auth_headers):
    assert client.get(f"/imports/{MISSING_ID}", headers=auth_headers).status_code == 404


# --- found in review ------------------------------------------------------------------------------------------------


def test_an_exported_file_of_an_english_speaking_family_is_read_back_the_same(client, db, user, auth_headers, queue):
    db.get(Families, user.family_id).language = "en"
    db.commit()

    _, saved = _read_back(client, queue, db, user, auth_headers, "03/02/2026;a;Aluguel;1,00;Débito")  # 3 February

    assert saved[0][0] == date(2026, 2, 3)


def test_an_excel_file_with_a_time_column_can_be_imported(client, db, user, auth_headers, queue):
    from datetime import time

    content = _xlsx(
        [
            ["Data", "Hora", "Descrição", "Categoria", "Valor"],
            [datetime(2026, 3, 15), time(10, 30), "Almoço", "Aluguel", 12.5],
        ]
    )
    uploaded = _upload(client, auth_headers, content, "extrato.xlsx")
    assert uploaded.status_code == 201, uploaded.text
    job = uploaded.json()["data"]
    assert job["sample"] == [["15/03/2026", "10:30:00", "Almoço", "Aluguel", "12.5"]]
    _match(client, auth_headers, job["id"], {"Data": 0, "Descrição": 2, "Categoria": 3, "Valor": 4, "Tipo": None})
    _start(client, auth_headers, job["id"])
    queue.run()

    assert _types(db, user) == [("Almoço", 1250, "debit")]


def test_a_damaged_excel_file_is_refused_with_a_message(client, auth_headers):
    import zipfile

    good = zipfile.ZipFile(io.BytesIO(_xlsx([["a"], ["b"]])))
    damaged = io.BytesIO()
    with zipfile.ZipFile(damaged, "w") as archive:
        for name in good.namelist():
            archive.writestr(name, b"<broken" if name.startswith("xl/worksheets/sheet1") else good.read(name))

    response = _upload(client, auth_headers, damaged.getvalue(), "extrato.xlsx")

    assert response.status_code == 422
    assert "Excel" in response.json()["detail"]


def test_an_upload_declared_over_the_limit_is_refused_before_anything_is_read(client, db):
    big = b"x" * (6 * 1024 * 1024)

    response = client.post("/imports", files={"file": ("grande.csv", big, "text/csv")})  # not even logged in

    assert response.status_code == 413
    assert "5 MB" in response.json()["detail"]
    assert db.query(ImportJobDB).count() == 0


def test_an_upload_under_the_limit_still_goes_through_the_size_check(client, auth_headers):
    assert _upload(client, auth_headers, _csv(GOOD_ROW)).status_code == 201


def test_a_nul_character_in_a_description_is_a_problem_not_a_failed_import():
    from api.services.import_service import check_table

    rows, problems = check_table(
        [["15/03/2026", "a\x00b", "Aluguel", "1,00"]],
        {"Data": 0, "Descrição": 1, "Categoria": 2, "Valor": 3, "Tipo": None},
        date(2026, 11, 3),
    )

    assert rows == []
    assert [p.row for p in problems] == [2]


def test_if_the_end_of_the_save_fails_after_the_rows_were_written_none_of_them_stay(
    client, db, user, auth_headers, queue, monkeypatch
):
    job = _stage(client, auth_headers, GOOD_ROW, "01/03/2026;Salário;Aluguel;5,00;Crédito")
    _start(client, auth_headers, job["id"])
    real = imports_controller.mark_done

    def fails_after_the_rows_were_sent_to_the_database(session, *args, **kwargs):
        session.flush()  # the rows are really in the transaction now
        assert db.query(TransactionDB).count() == 2
        raise RuntimeError("the database went away")

    monkeypatch.setattr(imports_controller, "mark_done", fails_after_the_rows_were_sent_to_the_database)

    queue.run()

    monkeypatch.setattr(imports_controller, "mark_done", real)
    after = client.get(f"/imports/{job['id']}", headers=auth_headers).json()["data"]
    assert after["status"] == "failed" and after["error"] == imports_controller.FAILED_MESSAGE
    assert _saved(db, user) == []


def test_starting_clears_stuck_jobs_before_taking_the_family_lock_and_commits_nothing_in_between(
    client, db, user, auth_headers, monkeypatch
):
    """A commit gives the row lock up. If one happened between the lock and queueing the job, two members pressing
    Import together could both pass the "one at a time" check."""
    from sqlalchemy.orm import Session

    job = _stage(client, auth_headers, GOOD_ROW)
    events = []
    real_lock, real_stuck, real_commit = (
        imports_controller.lock_family,
        imports_controller.fail_stuck_import_jobs,
        Session.commit,
    )

    monkeypatch.setattr(
        imports_controller,
        "fail_stuck_import_jobs",
        lambda *a, **k: (events.append("clear stuck"), real_stuck(*a, **k))[1],
    )
    monkeypatch.setattr(
        imports_controller, "lock_family", lambda *a, **k: (events.append("lock"), real_lock(*a, **k))[1]
    )
    monkeypatch.setattr(Session, "commit", lambda self: (events.append("commit"), real_commit(self))[1])
    real_queue = imports_controller.mark_queued
    monkeypatch.setattr(
        imports_controller, "mark_queued", lambda *a, **k: (events.append("queue"), real_queue(*a, **k))[1]
    )

    assert _start(client, auth_headers, job["id"]).status_code == 202

    assert events.index("clear stuck") < events.index("lock") < events.index("queue")
    assert (
        "commit" not in events[events.index("lock") : events.index("queue")]
    )  # the lock is held until the job is queued


def test_a_job_confirmed_just_now_does_not_expire_because_it_was_uploaded_long_ago(
    client, db, user, auth_headers, queue
):
    job = _stage(client, auth_headers, GOOD_ROW)
    _start(client, auth_headers, job["id"])
    row = db.get(ImportJobDB, job["id"])
    row.created_at = datetime.now() - timedelta(days=2)  # waited a long time for the person
    db.commit()

    assert client.get(f"/imports/{job['id']}", headers=auth_headers).status_code == 200
    _stage(client, auth_headers, "01/03/2026;Salário;Aluguel;5,00;Crédito")  # another upload cleans up old jobs
    assert db.query(ImportJobDB).filter_by(id=job["id"]).count() == 1
    queue.run()
    assert client.get(f"/imports/{job['id']}", headers=auth_headers).json()["data"]["status"] == "done"


# --- the person (TKT-73) ---------------------------------------------------------------------------------------------

PERSON_HEADER = "Data;Descrição;Categoria;Valor;Tipo;Pessoa"


def _partner(db, user, make_user, name="Bia Souza"):
    return make_user(name, family=db.get(Families, user.family_id))


def test_the_person_column_is_suggested_and_each_row_goes_to_the_person_it_names(
    client, db, user, auth_headers, make_user, queue
):
    partner = _partner(db, user, make_user)
    job = _upload(
        client,
        auth_headers,
        _csv(
            "15/03/2026;Mercado;Aluguel;10,00;Débito;  bia souza ",
            "16/03/2026;Padaria;Aluguel;5,00;Débito;",
            header=PERSON_HEADER,
        ),
    ).json()["data"]
    assert job["suggested_map"]["Pessoa"] == 5

    assert _match(client, auth_headers, job["id"], job["suggested_map"]).status_code == 200
    assert _start(client, auth_headers, job["id"]).status_code == 202
    queue.run()

    assert {t.label: t.user_id for t in _saved(db, user)} == {"Mercado": partner.id, "Padaria": user.id}


def _stage_people(client, headers, *lines):
    """Upload a file with a Pessoa column and match the columns the way the page suggests."""
    uploaded = _upload(client, headers, _csv(*lines, header=PERSON_HEADER)).json()["data"]
    response = _match(client, headers, uploaded["id"], uploaded["suggested_map"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _choose_people(client, headers, job_id, mapping):
    return client.put(f"/imports/{job_id}/people", json={"mapping": mapping}, headers=headers)


def test_a_name_that_matches_nobody_waits_for_the_person_to_choose_who_it_stands_for(
    client, db, user, auth_headers, make_user, queue
):
    partner = _partner(db, user, make_user)
    job = _stage_people(
        client,
        auth_headers,
        "15/03/2026;Mercado;Aluguel;10,00;Débito;Bia Souza",
        "16/03/2026;Padaria;Aluguel;5,00;Débito;Bia",
        "17/03/2026;Feira;Aluguel;3,00;Débito;bia",
        "18/03/2026;Café;Aluguel;2,00;Débito;",
    )

    assert job["unknown_people"] == [{"name": "Bia", "rows": 2, "user_id": None}]  # "bia" is the same name: asked once
    assert [(p["name"], p["user_id"]) for p in job["people"]] == [
        ("Bia Souza", str(partner.id)),
        ("Bia", None),
    ]  # all shown
    assert {m["id"] for m in job["members"]} == {str(user.id), str(partner.id)}
    assert _start(client, auth_headers, job["id"]).status_code == 409  # not before it is settled
    assert _saved(db, user) == []

    chosen = _choose_people(client, auth_headers, job["id"], {"bia": partner.id})

    assert chosen.status_code == 200
    assert chosen.json()["data"]["unknown_people"] == []
    assert _start(client, auth_headers, job["id"]).status_code == 202
    queue.run()
    assert {t.label: t.user_id for t in _saved(db, user)} == {
        "Mercado": partner.id,  # matched by itself
        "Padaria": partner.id,  # chosen
        "Feira": partner.id,  # chosen (the same name)
        "Café": user.id,  # empty: whoever imports
    }


def test_the_person_can_choose_themselves_for_a_name(client, db, user, auth_headers, queue):
    job = _stage_people(client, auth_headers, "15/03/2026;Mercado;Aluguel;10,00;Débito;Meu apelido")

    assert _choose_people(client, auth_headers, job["id"], {"Meu apelido": user.id}).status_code == 200
    _start(client, auth_headers, job["id"])
    queue.run()

    assert [t.user_id for t in _saved(db, user)] == [user.id]


def test_a_person_of_another_family_cannot_be_chosen(client, db, user, other_user, auth_headers):
    job = _stage_people(client, auth_headers, f"15/03/2026;Mercado;Aluguel;10,00;Débito;{other_user.name}")
    assert job["unknown_people"] == [
        {"name": other_user.name, "rows": 1, "user_id": None}
    ]  # not matched: not in this family

    refused = _choose_people(client, auth_headers, job["id"], {other_user.name: other_user.id})

    assert refused.status_code == 422
    assert _start(client, auth_headers, job["id"]).status_code == 409
    assert _saved(db, user) == []


def test_a_name_that_is_not_in_the_file_cannot_be_chosen(client, auth_headers, user):
    job = _stage_people(client, auth_headers, "15/03/2026;Mercado;Aluguel;10,00;Débito;Bia")

    assert _choose_people(client, auth_headers, job["id"], {"Outra": user.id}).status_code == 422


def test_two_people_with_the_same_name_are_not_guessed_but_asked(client, db, user, auth_headers, make_user):
    _partner(db, user, make_user, name=user.name)

    job = _stage_people(client, auth_headers, f"15/03/2026;Mercado;Aluguel;10,00;Débito;{user.name}")

    assert job["unknown_people"] == [{"name": user.name, "rows": 1, "user_id": None}]


def test_the_person_can_change_a_name_that_was_matched_by_itself(client, db, user, auth_headers, make_user, queue):
    partner = _partner(db, user, make_user)
    job = _stage_people(client, auth_headers, "15/03/2026;Mercado;Aluguel;10,00;Débito;Bia Souza")
    assert job["unknown_people"] == []
    assert job["people"] == [{"name": "Bia Souza", "rows": 1, "user_id": str(partner.id)}]  # matched, and shown

    changed = _choose_people(client, auth_headers, job["id"], {"Bia Souza": user.id})

    assert changed.status_code == 200
    assert changed.json()["data"]["people"][0]["user_id"] == str(user.id)
    _start(client, auth_headers, job["id"])
    queue.run()
    assert [t.user_id for t in _saved(db, user)] == [user.id]


def test_a_file_without_unknown_people_asks_nothing(client, auth_headers):
    job = _stage_people(
        client, auth_headers, "15/03/2026;Mercado;Aluguel;10,00;Débito;", "16/03/2026;Pão;Aluguel;1,00;Débito;"
    )

    assert job["unknown_people"] == []


# --- the merchant (TKT-58) -------------------------------------------------------------------------------------------

MERCHANT_HEADER = "Data;Descrição;Categoria;Valor;Tipo;Estabelecimento"


def _turn_merchants(client, headers, on=True):
    assert client.patch("/families/me/settings", json={"merchants_enabled": on}, headers=headers).status_code == 200


def _import_merchants(client, queue, headers, *lines):
    return _import_with_header(client, queue, headers, MERCHANT_HEADER, *lines)


def _import_with_header(client, queue, headers, header, *lines):
    uploaded = _upload(client, headers, _csv(*lines, header=header)).json()["data"]
    assert uploaded["suggested_map"]["Estabelecimento"] == 5
    assert _match(client, headers, uploaded["id"], uploaded["suggested_map"]).status_code == 200
    assert _start(client, headers, uploaded["id"]).status_code == 202
    queue.run()
    return client.get(f"/imports/{uploaded['id']}", headers=headers).json()["data"]


def _merchant_names(db, user):
    return {t.label: (db.get(Merchants, t.merchant_id).name if t.merchant_id else None) for t in _saved(db, user)}


def test_the_merchant_column_uses_the_merchants_the_family_has_and_creates_the_others(
    client, db, user, auth_headers, queue
):
    _turn_merchants(client, auth_headers)
    uber = Merchants(family_id=user.family_id, name="Uber")
    db.add(uber)
    db.commit()

    job = _import_merchants(
        client,
        queue,
        auth_headers,
        "15/03/2026;Corrida;Aluguel;10,00;Débito;  🚗 uber ",
        "16/03/2026;Pizza;Aluguel;20,00;Débito;iFood",
        "17/03/2026;Doce;Aluguel;5,00;Débito;IFOOD",
        "18/03/2026;Pão;Aluguel;1,00;Débito;",
    )

    assert job["status"] == "done"
    assert _merchant_names(db, user) == {"Corrida": "Uber", "Pizza": "iFood", "Doce": "iFood", "Pão": None}
    assert sorted(m.name for m in db.query(Merchants).filter_by(family_id=user.family_id)) == [
        "Uber",
        "iFood",
    ]  # one iFood
    assert {t.label: t.merchant_id for t in _saved(db, user)}["Corrida"] == uber.id  # the family's own was reused


def test_the_merchant_column_is_ignored_while_the_family_has_merchants_off(client, db, user, auth_headers, queue):
    job = _import_merchants(client, queue, auth_headers, "15/03/2026;Corrida;Aluguel;10,00;Débito;Uber")

    assert job["status"] == "done"
    assert _merchant_names(db, user) == {"Corrida": None}
    assert db.query(Merchants).count() == 0


def test_merchants_are_never_taken_from_or_created_in_another_family(
    client, db, user, other_user, auth_headers, headers_for, queue
):
    _turn_merchants(client, auth_headers)
    theirs = Merchants(family_id=other_user.family_id, name="Uber")
    db.add(theirs)
    db.commit()

    _import_merchants(client, queue, auth_headers, "15/03/2026;Corrida;Aluguel;10,00;Débito;Uber")

    [row] = _saved(db, user)
    assert row.merchant_id != theirs.id
    assert db.get(Merchants, row.merchant_id).family_id == user.family_id


def test_a_merchant_that_is_too_long_or_has_no_words_is_a_problem_of_its_row(client, db, user, auth_headers):
    uploaded = _upload(
        client,
        auth_headers,
        _csv(
            f"15/03/2026;Corrida;Aluguel;10,00;Débito;{'x' * 101}",
            "16/03/2026;Pizza;Aluguel;10,00;Débito;🍕",
            header=MERCHANT_HEADER,
        ),
    ).json()["data"]

    response = _match(client, auth_headers, uploaded["id"], uploaded["suggested_map"])

    assert response.status_code == 422
    assert [row for row, _message in _problems(response)] == [2, 3]
    assert db.query(Merchants).count() == 0


# --- categories of the file found by themselves, by their English or Portuguese names ----------------------------------


def test_english_names_of_the_default_categories_are_matched_by_themselves(client, db, user, auth_headers, queue):
    job = _stage(
        client,
        auth_headers,
        "15/03/2026;Weekly shop;Groceries;10,00;Débito",
        "15/03/2026;Dinner;Restaurants & Bars;20,00;Débito",
        "15/03/2026;Course;Education;30,00;Débito",
    )

    assert (job["unknown_categories"], job["new_categories"]) == ([], [])  # nobody has to choose anything
    assert _start(client, auth_headers, job["id"]).status_code == 202
    queue.run()
    names = {t.label: db.get(Categories, t.category_id).name for t in _saved(db, user)}
    assert names == {"Weekly shop": "Supermercado", "Dinner": "Restaurantes e Bares", "Course": "Educação"}


def test_portuguese_names_without_accents_or_in_another_case_are_matched_too(client, auth_headers):
    job = _stage(
        client,
        auth_headers,
        "15/03/2026;Curso;EDUCACAO;30,00;Débito",
        "15/03/2026;Mercado;mercado;10,00;Débito",
    )

    assert job["unknown_categories"] == []


def test_a_name_that_means_nothing_for_sure_is_still_asked_about(client, auth_headers):
    job = _stage(
        client, auth_headers, "15/03/2026;Ônibus;Transporte;10,00;Débito", "15/03/2026;Ração;Bicho;5,00;Débito"
    )

    assert sorted(item["name"] for item in job["unknown_categories"]) == ["Bicho", "Transporte"]


def test_a_category_the_family_really_has_wins_over_an_other_name(client, db, user, auth_headers, queue):
    """The family has its own "Groceries": the file's "Groceries" is that one, not the default Supermercado."""
    own = Categories(name="Groceries", family_id=user.family_id, group_id=db.query(CategoryGroups).first().id)
    db.add(own)
    db.commit()

    job = _import(client, queue, auth_headers, "15/03/2026;Shop;Groceries;10,00;Débito")

    assert job["status"] == "done"
    assert [t.category_id for t in _saved(db, user)] == [own.id]


def test_an_other_name_of_a_default_that_is_not_there_is_not_matched(client, auth_headers):
    """ "Pets" is deliberately not seeded in the tests: its English name ("Pet Care") has nothing to point at."""
    job = _stage(client, auth_headers, "15/03/2026;Vet;Pet Care;50,00;Débito")

    assert [item["name"] for item in job["unknown_categories"]] == ["Pet Care"]

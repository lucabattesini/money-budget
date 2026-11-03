"""Export jobs: POST /exports queues the work, GET /exports/{id} shows its state, .../file downloads it.

The background task is held back by the `queue` fixture and run on demand, so tests can see a job
while it is still queued and then let it finish.
"""

import io
from datetime import datetime, timedelta

import pytest
from openpyxl import load_workbook

from api.controllers import exports_controller
from api.routers import exports_router
from schemas.tables import ExportJobDB


@pytest.fixture
def queue(monkeypatch):
    """Collect the jobs the API schedules; `queue.run()` does the background work."""
    pending = []
    monkeypatch.setattr(exports_router, "run_export_job", pending.append)

    class Queue:
        @staticmethod
        def run():
            while pending:
                exports_controller.run_export_job(pending.pop(0))

    return Queue()


def _run(client, queue, headers, file_format=None):
    """Queue an export, let the background work finish, and return the job id."""
    job_id = _queue(client, headers, file_format).json()["data"]["id"]
    queue.run()
    return job_id


def _queue(client, headers, file_format=None):
    body = {} if file_format is None else {"format": file_format}
    return client.post("/exports", json=body, headers=headers)


def _file(client, headers, job_id):
    return client.get(f"/exports/{job_id}/file", headers=headers)


def _csv_rows(response):
    return response.content.decode("utf-8-sig").split("\r\n")[:-1]


# --- queueing and status -----------------------------------------------------


def test_queueing_answers_accepted_and_the_job_waits_until_the_background_work_runs(
    client, user, auth_headers, db, queue
):
    response = _queue(client, auth_headers, "xlsx")

    assert response.status_code == 202
    job = response.json()["data"]
    assert (job["format"], job["id"]) == ("xlsx", db.query(ExportJobDB).one().id)
    assert job["status"] == "queued"
    still_waiting = client.get(f"/exports/{job['id']}", headers=auth_headers).json()["data"]
    assert (still_waiting["status"], still_waiting["filename"]) == ("queued", None)


def test_the_job_is_done_once_the_background_work_has_run(client, user, auth_headers, queue):
    job_id = _run(client, queue, auth_headers)

    job = client.get(f"/exports/{job_id}", headers=auth_headers).json()["data"]

    assert job["status"] == "done"
    assert job["filename"].startswith("transacoes-") and job["filename"].endswith(".csv")
    assert job["finished_at"] is not None
    assert job["error"] is None
    assert "content" not in job  # the file is not part of the status


def test_the_format_defaults_to_csv(client, auth_headers, queue):
    assert _queue(client, auth_headers).json()["data"]["format"] == "csv"


@pytest.mark.parametrize("file_format", ["pdf", "XLSX", ""])
def test_queueing_rejects_an_unknown_format(client, db, auth_headers, file_format):
    assert _queue(client, auth_headers, file_format).status_code == 422
    assert db.query(ExportJobDB).count() == 0


# --- the file ------------------------------------------------------------------


def test_csv_file_has_the_documented_columns_and_brazilian_formatting(
    client, user, auth_headers, make_transaction, category_ids, queue
):
    make_transaction(user, category_ids["Restaurantes e Bares"], label="Almoço", value=123456, when=datetime(2026, 3, 15, 12, 0))
    make_transaction(
        user, category_ids["Transporte público"], label="Salário", value=5, when=datetime(2026, 3, 1), type="credit"
    )
    job_id = _run(client, queue, auth_headers, "csv")

    response = _file(client, auth_headers, job_id)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="transacoes-')
    assert _csv_rows(response) == [
        "Data;Descrição;Categoria;Valor;Tipo",
        "15/03/2026;Almoço;Restaurantes e Bares;1.234,56;Débito",
        "01/03/2026;Salário;Transporte público;0,05;Crédito",
    ]


def test_xlsx_file_has_real_dates_and_numbers(client, user, auth_headers, make_transaction, category_ids, queue):
    make_transaction(user, category_ids["Restaurantes e Bares"], label="Almoço", value=123456, when=datetime(2026, 3, 15, 12, 0))
    job_id = _run(client, queue, auth_headers, "xlsx")

    response = _file(client, auth_headers, job_id)

    assert response.headers["content-disposition"].endswith('.xlsx"')
    sheet = load_workbook(io.BytesIO(response.content)).active
    assert [c.value for c in sheet[1]] == ["Data", "Descrição", "Categoria", "Valor", "Tipo"]
    when, label, category, amount, kind = sheet[2]
    assert (when.value, label.value, category.value, amount.value, kind.value) == (
        datetime(2026, 3, 15, 12, 0),
        "Almoço",
        "Restaurantes e Bares",
        1234.56,
        "Débito",
    )


def test_the_file_only_contains_the_callers_transactions(
    client, user, other_user, auth_headers, make_transaction, category_ids, queue
):
    food = category_ids["Restaurantes e Bares"]
    make_transaction(user, food, label="Meu")
    make_transaction(other_user, food, label="Segredo do outro")
    job_id = _run(client, queue, auth_headers)

    text = _file(client, auth_headers, job_id).content.decode("utf-8-sig")

    assert "Meu" in text
    assert "Segredo do outro" not in text


def test_the_file_has_every_transaction_not_just_one_page(client, db, user, auth_headers, queue):
    from schemas.tables import TransactionDB

    db.add_all(
        TransactionDB(
            family_id=user.family_id,
            user_id=user.id,
            label=f"t{i}",
            value=100,
            transactioned_at=datetime(2026, 1, 1),
            category_id=None,
        )
        for i in range(250)
    )
    db.commit()
    job_id = _run(client, queue, auth_headers)

    assert len(_csv_rows(_file(client, auth_headers, job_id))) == 1 + 250


def test_the_file_lists_the_newest_first_and_shows_a_missing_category_as_empty(
    client, user, auth_headers, make_transaction, queue
):
    make_transaction(user, None, label="velha", when=datetime(2026, 1, 1))
    make_transaction(user, None, label="nova", when=datetime(2026, 3, 1))
    job_id = _run(client, queue, auth_headers)

    rows = _csv_rows(_file(client, auth_headers, job_id))

    assert [r.split(";")[1] for r in rows[1:]] == ["nova", "velha"]
    assert rows[1].split(";")[2] == ""


def test_an_export_without_transactions_is_just_the_header(client, auth_headers, queue):
    job_id = _run(client, queue, auth_headers)

    assert _csv_rows(_file(client, auth_headers, job_id)) == ["Data;Descrição;Categoria;Valor;Tipo"]


def test_a_description_cannot_run_as_a_formula(client, user, auth_headers, make_transaction, category_ids, queue):
    make_transaction(user, category_ids["Restaurantes e Bares"], label='=HYPERLINK("http://evil")')
    job_id = _run(client, queue, auth_headers)

    assert "'=HYPERLINK" in _file(client, auth_headers, job_id).content.decode("utf-8-sig")


# --- not ready, failed, someone else's -----------------------------------------------


def test_the_file_is_not_available_before_the_job_is_done(client, db, user, auth_headers):
    job = ExportJobDB(family_id=user.family_id, requested_by=user.id, format="csv", status="queued")
    db.add(job)
    db.commit()

    response = _file(client, auth_headers, job.id)

    assert response.status_code == 409
    assert "queued" in response.json()["detail"]


def test_a_failing_job_is_marked_failed_with_a_message_and_has_no_file(
    client, db, user, auth_headers, monkeypatch, queue
):
    def boom(*args, **kwargs):
        raise RuntimeError("internal detail that must not reach the user")

    monkeypatch.setattr(exports_controller, "export_transactions", boom)
    job_id = _run(client, queue, auth_headers)

    job = client.get(f"/exports/{job_id}", headers=auth_headers).json()["data"]

    assert job["status"] == "failed"
    assert job["error"] == "Não foi possível gerar o arquivo."
    assert "internal detail" not in job["error"]
    assert _file(client, auth_headers, job_id).status_code == 409


def test_another_user_cannot_see_or_download_a_job(client, user, other_user, auth_headers, headers_for, queue):
    job_id = _run(client, queue, auth_headers)

    assert client.get(f"/exports/{job_id}", headers=headers_for(other_user)).status_code == 404
    assert _file(client, headers_for(other_user), job_id).status_code == 404


def test_an_unknown_job_is_not_found(client, auth_headers):
    assert client.get("/exports/999999", headers=auth_headers).status_code == 404
    assert _file(client, auth_headers, 999999).status_code == 404


def test_queueing_deletes_every_expired_job_not_just_the_callers_but_keeps_recent_ones(
    client, db, user, other_user, auth_headers, queue
):
    ancient = datetime(2020, 1, 1)
    db.add_all(
        [
            ExportJobDB(
                family_id=user.family_id,
                requested_by=user.id,
                format="csv",
                status="done",
                content=b"x",
                created_at=ancient,
            ),
            ExportJobDB(
                family_id=other_user.family_id,
                requested_by=other_user.id,
                format="csv",
                status="done",
                content=b"y",
                created_at=ancient,
            ),
            ExportJobDB(
                family_id=other_user.family_id,
                requested_by=other_user.id,
                format="csv",
                status="done",
                content=b"z",
                created_at=datetime.now(),
            ),
        ]
    )
    db.commit()

    _queue(client, auth_headers)

    db.expire_all()
    remaining = db.query(ExportJobDB).order_by(ExportJobDB.id).all()
    assert [(j.requested_by, j.content) for j in remaining[:1]] == [(other_user.id, b"z")]  # the recent one survives
    assert len(remaining) == 2  # that one and the job just queued


def test_an_expired_job_and_its_file_are_gone_even_if_nobody_queued_anything_since(client, db, user, auth_headers):
    old = ExportJobDB(
        family_id=user.family_id,
        requested_by=user.id,
        format="csv",
        status="done",
        filename="a.csv",
        media_type="text/csv",
        content=b"x",
        created_at=datetime(2020, 1, 1),
    )
    db.add(old)
    db.commit()

    assert client.get(f"/exports/{old.id}", headers=auth_headers).status_code == 404
    assert _file(client, auth_headers, old.id).status_code == 404


# --- one at a time, stuck jobs ---------------------------------------------------------


def test_a_second_export_is_refused_while_one_is_waiting_and_allowed_when_it_finishes(
    client, db, user, auth_headers, queue
):
    first = _queue(client, auth_headers)
    assert first.status_code == 202

    second = _queue(client, auth_headers)

    assert second.status_code == 409
    assert "andamento" in second.json()["detail"]
    assert db.query(ExportJobDB).count() == 1  # nothing extra was stored

    queue.run()
    assert _queue(client, auth_headers).status_code == 202


def test_the_limit_is_per_user(client, db, user, other_user, auth_headers, headers_for, queue):
    assert _queue(client, auth_headers).status_code == 202

    assert _queue(client, headers_for(other_user)).status_code == 202


def test_a_job_stuck_in_queued_or_running_is_cancelled_and_no_longer_blocks_new_exports(
    client, db, user, auth_headers, queue
):
    stuck = ExportJobDB(
        family_id=user.family_id,
        requested_by=user.id,
        format="csv",
        status="running",
        created_at=datetime.now() - timedelta(minutes=10),
    )
    db.add(stuck)
    db.commit()

    job = client.get(f"/exports/{stuck.id}", headers=auth_headers).json()["data"]
    assert job["status"] == "failed"
    assert "cancelada" in job["error"]
    assert _queue(client, auth_headers).status_code == 202


def test_a_new_export_is_not_blocked_by_a_stuck_one(client, db, user, auth_headers, queue):
    db.add(
        ExportJobDB(
            family_id=user.family_id,
            requested_by=user.id,
            format="csv",
            status="queued",
            created_at=datetime.now() - timedelta(minutes=10),
        )
    )
    db.commit()

    assert _queue(client, auth_headers).status_code == 202


def test_a_job_that_is_only_a_little_old_is_not_cancelled(client, db, user, auth_headers):
    recent = ExportJobDB(
        family_id=user.family_id,
        requested_by=user.id,
        format="csv",
        status="running",
        created_at=datetime.now() - timedelta(minutes=1),
    )
    db.add(recent)
    db.commit()

    assert client.get(f"/exports/{recent.id}", headers=auth_headers).json()["data"]["status"] == "running"


# --- the runner -------------------------------------------------------------------------


def test_the_runner_ignores_a_job_that_no_longer_exists():
    exports_controller.run_export_job(999999)  # must not raise


def test_the_runner_does_not_crash_when_even_recording_the_failure_fails(
    client, db, user, auth_headers, monkeypatch, queue
):
    def boom(*args, **kwargs):
        raise RuntimeError("database gone")

    job_id = _queue(client, auth_headers).json()["data"]["id"]
    monkeypatch.setattr(exports_controller, "export_transactions", boom)
    monkeypatch.setattr(exports_controller, "mark_failed", boom)

    exports_controller.run_export_job(job_id)  # must not raise

    db.expire_all()
    assert db.query(ExportJobDB).filter_by(id=job_id).one().status == "running"  # reaped later as stuck


def test_asking_for_the_status_does_not_load_the_file(db, user):
    from sqlalchemy import inspect

    from api.repositories.exports_repo import get_export_job
    from db.connection import session_scope

    job = ExportJobDB(family_id=user.family_id, requested_by=user.id, format="csv", status="done", content=b"x" * 1000)
    db.add(job)
    db.commit()

    with session_scope() as fresh:  # a new session: nothing is cached yet
        assert "content" in inspect(get_export_job(fresh, job.id)).unloaded
    with session_scope() as fresh:
        assert get_export_job(fresh, job.id, with_file=True).content == b"x" * 1000


# --- more ownership and formula checks ---------------------------------------------------


def test_another_user_cannot_see_a_job_that_is_still_queued(client, user, other_user, auth_headers, headers_for, queue):
    job_id = _queue(client, auth_headers).json()["data"]["id"]

    assert client.get(f"/exports/{job_id}", headers=headers_for(other_user)).status_code == 404


def test_a_category_name_and_the_excel_file_cannot_run_as_a_formula(client, db, user, auth_headers, queue):
    from schemas.tables import Categories, TransactionDB

    category = Categories(name="=SUM(A1:A9)")
    db.add(category)
    db.commit()
    db.add(
        TransactionDB(
            family_id=user.family_id,
            user_id=user.id,
            label="+cmd",
            value=100,
            transactioned_at=datetime(2026, 3, 15),
            category_id=category.id,
        )
    )
    db.commit()
    job_id = _run(client, queue, auth_headers, "xlsx")

    sheet = load_workbook(io.BytesIO(_file(client, auth_headers, job_id).content)).active

    description, category_cell = sheet["B2"], sheet["C2"]
    assert (description.value, category_cell.value) == ("'+cmd", "'=SUM(A1:A9)")
    assert description.data_type == "s" and category_cell.data_type == "s"  # text, never a formula


@pytest.mark.parametrize("method, path", [("post", "/exports"), ("get", "/exports/1"), ("get", "/exports/1/file")])
def test_exports_require_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401

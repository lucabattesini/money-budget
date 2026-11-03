import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.gateways.documents import MAX_FILE_BYTES, UnreadableDocument, get_document_gateway
from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
from api.repositories.categories_repo import lock_family
from api.repositories.imports_repo import (
    add_transactions,
    create_import_job,
    delete_job,
    delete_old_import_jobs,
    delete_staged_jobs_of,
    existing_transaction_keys,
    fail_stuck_import_jobs,
    get_import_job,
    has_active_import_job,
    is_expired,
    mark_done,
    mark_failed,
    mark_queued,
    mark_running,
    set_category_map,
)
from api.services.import_service import MissingColumns, check_table
from api.utils.category_names import name_key
from db.connection import session_scope
from schemas.tables import ImportJobDB

logger = logging.getLogger(__name__)

FAILED_MESSAGE = "Não foi possível importar o arquivo."
STUCK_MESSAGE = "A importação demorou demais e foi cancelada."
FORMATS = {".xlsx": "xlsx", ".csv": "csv"}
MAX_PROBLEMS_SHOWN = 200  # a file with thousands of mistakes still gets an answer of a sensible size
MAX_SKIPPED_SHOWN = 100


class ImportRejected(Exception):
    """The file was read but has rows with problems: nothing was kept. The problems are for the person to fix."""

    def __init__(self, message: str, problems: list[dict], total: int):
        super().__init__(message)
        self.message, self.problems, self.total = message, problems, total


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


# --- categories ----------------------------------------------------------------------------------------------------


def _category_lookup(db: Session, family_id: int) -> tuple[dict[str, int], set[int]]:
    """(words of the name -> category id, every id the family may use). The family's own category wins over a default
    one with the same name."""
    categories = [category for category, _group in get_all_categories_repo(db, family_id)]
    lookup: dict[str, int] = {}
    for category in sorted(categories, key=lambda c: c.family_id is not None):  # defaults first, then overwritten
        lookup[name_key(category.name)] = category.id
    return lookup, {category.id for category in categories}


def _resolve(job: ImportJobDB, lookup: dict[str, int], visible: set[int]) -> tuple[dict[str, int], dict[str, dict]]:
    """(file category -> id, the file categories still without one). A name the family has (now) needs no choice; for
    the others, the choice the person made counts as long as that category is still there."""
    chosen = job.category_map or {}
    resolved: dict[str, int] = {}
    unknown: dict[str, dict] = {}
    for row in job.rows or []:
        key = name_key(row["category"])
        if key in resolved:
            continue
        category_id = lookup.get(key) or (chosen.get(key) if chosen.get(key) in visible else None)
        if category_id is not None:
            resolved[key] = category_id
        else:
            unknown.setdefault(key, {"name": row["category"], "rows": 0})
    for row in job.rows or []:
        key = name_key(row["category"])
        if key in unknown:
            unknown[key]["rows"] += 1
    return resolved, unknown


def _duplicates(db: Session, job: ImportJobDB, resolved: dict[str, int]) -> list[dict]:
    """The rows the family already has (same day, description, amount, category and type). Rows of the same file
    never count as duplicates of each other."""
    rows = [row for row in job.rows or [] if name_key(row["category"]) in resolved]
    if not rows:
        return []
    days = [date.fromisoformat(row["date"]) for row in rows]
    saved = existing_transaction_keys(db, job.family_id, min(days), max(days))
    return [
        row
        for row in rows
        if (date.fromisoformat(row["date"]), row["label"], row["value"], resolved[name_key(row["category"])], row["type"])
        in saved
    ]


# --- the job as the person sees it -----------------------------------------------------------------------------


def describe_job(db: Session, job: ImportJobDB) -> dict:
    out = {
        "id": job.id,
        "status": job.status,
        "filename": job.filename,
        "total_rows": job.total_rows,
        "imported_count": job.imported_count,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
    if job.status == "staged":
        lookup, visible = _category_lookup(db, job.family_id)
        resolved, unknown = _resolve(job, lookup, visible)
        duplicates = _duplicates(db, job, resolved)
        out.update(
            unknown_categories=list(unknown.values()),
            skipped_count=len(duplicates),
            skipped=duplicates[:MAX_SKIPPED_SHOWN],
            to_import=job.total_rows - len(duplicates),
        )
    elif job.status == "done":
        skipped = job.skipped or []
        out.update(skipped_count=len(skipped), skipped=skipped[:MAX_SKIPPED_SHOWN])
    return out


# --- steps ---------------------------------------------------------------------------------------------------------


def stage_import(db: Session, family_id: int, user_id: int, filename: str, content: bytes) -> dict:
    """Step 1: read and check the whole file. Nothing is saved as transactions; the checked rows wait for the next step."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in FORMATS:
        raise _unprocessable("Envie um arquivo .xlsx (Excel) ou .csv.")
    if len(content) > MAX_FILE_BYTES:
        raise _unprocessable("O arquivo é grande demais (o máximo é 5 MB).")

    try:
        table = get_document_gateway(FORMATS[extension]).read(content)
        rows, problems = check_table(table, date.today())
    except (UnreadableDocument, MissingColumns) as error:
        raise _unprocessable(str(error)) from None
    if problems:
        shown = [{"row": p.row, "message": p.message} for p in problems[:MAX_PROBLEMS_SHOWN]]
        raise ImportRejected("O arquivo tem problemas. Nada foi importado.", shown, len(problems))
    if not rows:
        raise _unprocessable("O arquivo não tem nenhuma transação.")

    delete_old_import_jobs(db)
    delete_staged_jobs_of(db, family_id, user_id)
    return describe_job(db, create_import_job(db, family_id, user_id, filename, rows))


def get_import(db: Session, job_id: int, family_id: int, user_id: int) -> ImportJobDB:
    job = get_import_job(db, job_id, family_id, user_id)
    # Missing, another family's, another person's and expired all look the same, so ids of other users are not revealed
    if job is None or is_expired(job, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    if job.status in ("queued", "running"):
        fail_stuck_import_jobs(db, family_id, STUCK_MESSAGE)
        db.refresh(job)
    return job


def _staged(db: Session, job_id: int, family_id: int, user_id: int) -> ImportJobDB:
    job = get_import(db, job_id, family_id, user_id)
    if job.status != "staged":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Essa importação já foi iniciada.")
    return job


def choose_categories(db: Session, job_id: int, family_id: int, user_id: int, mapping: dict[str, int]) -> ImportJobDB:
    """Step 2: say which category of the family each unknown name in the file stands for."""
    job = _staged(db, job_id, family_id, user_id)
    _lookup, visible = _category_lookup(db, family_id)
    in_file = {name_key(row["category"]) for row in job.rows}
    chosen = dict(job.category_map or {})
    for name, category_id in mapping.items():
        if name_key(name) not in in_file:
            raise _unprocessable(f'A categoria "{name}" não está no arquivo.')
        if category_id not in visible:
            raise _unprocessable("Essa categoria não existe.")
        chosen[name_key(name)] = category_id
    set_category_map(db, job, chosen)
    return job


def cancel_import(db: Session, job_id: int, family_id: int, user_id: int) -> None:
    delete_job(db, _staged(db, job_id, family_id, user_id))


def start_import(db: Session, job_id: int, family_id: int, user_id: int) -> ImportJobDB:
    """Step 3: queue the import. The transactions are saved later by run_import_job.

    One import at a time per family. The family row is locked so two clicks cannot both get through the check.
    """
    lock_family(db, family_id)
    job = _staged(db, job_id, family_id, user_id)
    fail_stuck_import_jobs(db, family_id, STUCK_MESSAGE)
    if has_active_import_job(db, family_id):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe uma importação em andamento na sua família."
        )
    lookup, visible = _category_lookup(db, family_id)
    _resolved, unknown = _resolve(job, lookup, visible)
    if unknown:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ainda há categorias do arquivo sem uma categoria escolhida."
        )
    mark_queued(db, job)
    return job


def run_import_job(job_id: int) -> None:
    """Save the transactions of a queued job. Runs in the background, after the response was sent.

    All or nothing: the transactions and the "done" mark are committed together.
    """
    with session_scope() as db:
        job = get_import_job(db, job_id)
        if job is None or job.status != "queued":
            return
        try:
            mark_running(db, job)
            lookup, visible = _category_lookup(db, job.family_id)
            resolved, unknown = _resolve(job, lookup, visible)
            if unknown:  # a category was deleted after the person chose
                mark_failed(db, job, "Uma categoria do arquivo deixou de existir. Comece de novo.")
                return
            duplicates = _duplicates(db, job, resolved)
            skipped_rows = {row["row"] for row in duplicates}
            add_transactions(
                db,
                job.family_id,
                job.requested_by,
                [
                    {**row, "category_id": resolved[name_key(row["category"])]}
                    for row in job.rows
                    if row["row"] not in skipped_rows
                ],
            )
            mark_done(db, job, len(job.rows) - len(duplicates), duplicates)
        except Exception:
            logger.exception("Import job %s failed", job_id)
            try:
                db.rollback()
                mark_failed(db, job, FAILED_MESSAGE)
            except Exception:
                # Even recording the failure failed (database down?). The job is reaped as stuck later.
                logger.exception("Could not mark import job %s as failed", job_id)

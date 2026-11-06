import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.gateways.documents import MAX_FILE_BYTES, UnreadableDocument, get_document_gateway
from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
from api.repositories.categories_repo import lock_family
from api.repositories.families_repo import get_family, list_members
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
    set_checked_rows,
    set_rows,
)
from api.services.import_service import (
    DATE_ORDERS,
    SIGNS,
    TYPE_COLUMN,
    check_table,
    display_cell,
    encode_cell,
    mapping_problem,
    resolve_date_order,
    simple_name,
    suggest_mapping,
    suggest_sign,
)
from api.utils.category_names import name_key
from api.utils.clock import family_today
from api.utils.formatting import AMOUNT_STYLES
from db.connection import session_scope
from schemas.tables import ImportJobDB, Merchants

logger = logging.getLogger(__name__)

FAILED_MESSAGE = "Não foi possível importar o arquivo."
STUCK_MESSAGE = "A importação demorou demais e foi cancelada."
FORMATS = {".xlsx": "xlsx", ".csv": "csv"}
MAX_PROBLEMS_SHOWN = 200  # a file with thousands of mistakes still gets an answer of a sensible size
MAX_SKIPPED_SHOWN = 100
SAMPLE_ROWS = 5  # rows of the file shown while the person matches the columns


class ImportRejected(Exception):
    """The file has rows with problems under the chosen columns: nothing was kept. The problems are for the person to fix."""

    def __init__(self, message: str, problems: list[dict], total: int):
        super().__init__(message)
        self.message, self.problems, self.total = message, problems, total


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


# --- categories ----------------------------------------------------------------------------------------------------


def _member_names(db: Session, family_id: int) -> dict[str, int | None]:
    """(name of each person of the family, as simple_name writes it -> their id). Two people with the same name map to
    None, so a file naming them is refused instead of guessed."""
    names: dict[str, int | None] = {}
    for member in list_members(db, family_id):
        key = simple_name(member.name)
        names[key] = None if key in names else member.id
    return names


def _file_people(job: ImportJobDB) -> dict[str, dict]:
    """(name of the file as simple_name writes it -> {name, rows, user_id}) for each person named in the Pessoa column.
    `user_id` is the member the name was matched to by itself or that the person chose, None while there is none.
    An empty cell is not a person: it means whoever imports."""
    people: dict[str, dict] = {}
    for row in job.rows or []:
        if row.get("person"):
            entry = people.setdefault(
                simple_name(row["person"]), {"name": row["person"], "rows": 0, "user_id": row.get("user_id")}
            )
            entry["rows"] += 1
    return people


def _same_rows(old: list[dict], new: list[dict]) -> bool:
    """True if the checked rows say the same thing, whoever the person chose for a name since."""

    def plain(rows):
        return [{key: value for key, value in row.items() if key != "user_id"} for row in rows]

    return plain(old) == plain(new)


def _unknown_people(job: ImportJobDB) -> dict[str, dict]:
    """The names of the file that no member stands for yet: the person has to choose."""
    return {key: entry for key, entry in _file_people(job).items() if entry["user_id"] is None}


def _merchant_ids(db: Session, family_id: int, names: set[str]) -> dict[str, int]:
    """(words of the name -> merchant id) for each merchant of the file: the family's own when one has the same words
    (ignoring case, spaces and emoji), otherwise a new one, created here. Not committed: it goes with the import, so
    either everything is saved or nothing is."""
    lookup = {name_key(m.name): m.id for m in db.query(Merchants).filter(Merchants.family_id == family_id)}
    for name in sorted(names):  # in a fixed order, so the same file always creates them in the same order
        if name_key(name) not in lookup:
            merchant = Merchants(family_id=family_id, name=name)
            db.add(merchant)
            db.flush()
            lookup[name_key(name)] = merchant.id
    return lookup


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


def _new_categories(job: ImportJobDB, lookup: dict[str, int], visible: set[int]) -> list[dict]:
    """Every category of the file the family does not have by that name, with the category the person chose for it
    (`category_id`, None while there is none). The step lists all of them, so choices can be seen and changed."""
    chosen = job.category_map or {}
    found: dict[str, dict] = {}
    for row in job.rows or []:
        key = name_key(row["category"])
        if key in lookup:
            continue
        entry = found.setdefault(
            key,
            {
                "name": row["category"],
                "rows": 0,
                "category_id": chosen.get(key) if chosen.get(key) in visible else None,
            },
        )
        entry["rows"] += 1
    return list(found.values())


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
        if (
            date.fromisoformat(row["date"]),
            row["label"],
            row["value"],
            resolved[name_key(row["category"])],
            row["type"],
        )
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
    if job.status == "staged" and job.rows is None:
        # Read, but the person has not said which column is which yet
        sample = [row for row in job.raw_rows if any(cell is not None for cell in row)][:SAMPLE_ROWS]
        out.update(
            columns=job.columns,
            suggested_map=suggest_mapping(job.columns),
            suggested_sign=suggest_sign(job.raw_rows, suggest_mapping(job.columns)),
            sample=[[display_cell(cell) for cell in row] for row in sample],
        )
    elif job.status == "staged":
        lookup, visible = _category_lookup(db, job.family_id)
        resolved, unknown = _resolve(job, lookup, visible)
        duplicates = _duplicates(db, job, resolved)
        out.update(
            columns=job.columns,
            column_map=job.column_map,
            unknown_categories=list(unknown.values()),
            new_categories=_new_categories(job, lookup, visible),
            people=list(_file_people(job).values()),
            unknown_people=list(_unknown_people(job).values()),
            members=[{"id": m.id, "name": m.name} for m in list_members(db, job.family_id)],
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
    """Step 1: read the file. Nothing is checked yet: the person first says which column is which."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in FORMATS:
        raise _unprocessable("Envie um arquivo .xlsx (Excel) ou .csv.")
    if len(content) > MAX_FILE_BYTES:
        raise _unprocessable("O arquivo é grande demais (o máximo é 5 MB).")

    try:
        table = get_document_gateway(FORMATS[extension]).read(content)
    except UnreadableDocument as error:
        raise _unprocessable(str(error)) from None
    if not any(cell is not None for row in table.rows for cell in row):
        raise _unprocessable("O arquivo não tem nenhuma transação.")

    delete_old_import_jobs(db)
    delete_staged_jobs_of(db, family_id, user_id)
    raw_rows = [[encode_cell(cell) for cell in row] for row in table.rows]
    return describe_job(db, create_import_job(db, family_id, user_id, filename, table.columns, raw_rows))


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


def _checked(job: ImportJobDB) -> ImportJobDB:
    if job.rows is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diga primeiro qual coluna do arquivo é qual.")
    return job


def match_columns(
    db: Session,
    job_id: int,
    family_id: int,
    user_id: int,
    mapping: dict[str, int | None],
    date_order: str = "auto",
    amount_style: str = "auto",
    sign: str = TYPE_COLUMN,
) -> tuple[ImportJobDB, str]:
    """Step 2: which column of the file holds each field. Then every row is checked; if any is wrong nothing is kept
    (the job stays as it was, so the person can match differently or send another file). Also answers how the dates
    written as text were read."""
    job = _staged(db, job_id, family_id, user_id)
    problem = mapping_problem(mapping, len(job.columns))
    if problem:
        raise _unprocessable(problem)
    if date_order not in DATE_ORDERS or amount_style not in AMOUNT_STYLES or sign not in SIGNS:
        raise _unprocessable("Formato desconhecido.")
    if sign != TYPE_COLUMN and mapping.get("Tipo") is not None:
        raise _unprocessable("Com o sinal do valor dizendo se é débito ou crédito, não escolha uma coluna para o Tipo.")
    order = resolve_date_order(job.raw_rows, mapping["Data"], date_order)
    rows, problems = check_table(
        job.raw_rows,
        mapping,
        family_today(get_family(db, family_id).timezone),
        order,
        amount_style,
        sign,
        strict_dates=date_order != "auto",
        members=_member_names(db, family_id),
    )
    if problems:
        shown = [{"row": p.row, "message": p.message} for p in problems[:MAX_PROBLEMS_SHOWN]]
        raise ImportRejected("O arquivo tem problemas. Nada foi importado.", shown, len(problems))
    if not rows:
        raise _unprocessable("O arquivo não tem nenhuma transação.")
    column_map = {field: mapping.get(field) for field in mapping}
    if job.rows is not None and job.column_map == column_map and _same_rows(job.rows, rows):
        return job, order  # nothing changed: what the person chose about categories and people stays as it is
    members = {member.id for member in list_members(db, family_id)}
    chosen = {
        simple_name(row["person"]): row["user_id"]
        for row in job.rows or []
        if row.get("person") and row.get("user_id") in members
    }
    # A name the person already settled keeps its member, even if the columns changed
    rows = [
        {**row, "user_id": chosen[simple_name(row["person"])]}
        if row.get("person") and simple_name(row["person"]) in chosen
        else row
        for row in rows
    ]
    set_checked_rows(db, job, column_map, rows)
    return job, order


def choose_categories(db: Session, job_id: int, family_id: int, user_id: int, mapping: dict[str, int]) -> ImportJobDB:
    """Step 3: say which category of the family each unknown name in the file stands for."""
    job = _checked(_staged(db, job_id, family_id, user_id))
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


def choose_people(db: Session, job_id: int, family_id: int, user_id: int, mapping: dict[str, int]) -> ImportJobDB:
    """Step 3b: say which member of the family each name of the Pessoa column stands for. It can change the ones matched
    by themselves too: the person always has the last word."""
    job = _checked(_staged(db, job_id, family_id, user_id))
    members = {member.id for member in list_members(db, family_id)}
    in_file = _file_people(job)
    chosen: dict[str, int] = {}
    for name, person_id in mapping.items():
        if simple_name(name) not in in_file:
            raise _unprocessable(f'A pessoa "{name}" não está no arquivo.')
        if person_id not in members:
            raise _unprocessable("Essa pessoa não é da sua família.")
        chosen[simple_name(name)] = person_id
    set_rows(
        db,
        job,
        [
            {**row, "user_id": chosen[simple_name(row["person"])]}
            if row.get("person") and simple_name(row["person"]) in chosen
            else row
            for row in job.rows
        ],
    )
    return job


def cancel_import(db: Session, job_id: int, family_id: int, user_id: int) -> None:
    delete_job(db, _staged(db, job_id, family_id, user_id))


def start_import(db: Session, job_id: int, family_id: int, user_id: int) -> ImportJobDB:
    """Step 4: queue the import. The transactions are saved later by run_import_job.

    One import at a time per family. The family row is locked so two clicks cannot both get through the check. Nothing
    may commit between taking the lock and queueing the job (a commit gives the lock up), so stuck jobs are cleared first.
    """
    fail_stuck_import_jobs(db, family_id, STUCK_MESSAGE)  # commits: before the lock
    lock_family(db, family_id)
    job = _checked(_staged(db, job_id, family_id, user_id))
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
    if _unknown_people(job):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ainda há pessoas do arquivo sem uma pessoa da família escolhida.",
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
            people = {member.id for member in list_members(db, job.family_id)}
            if any(row.get("user_id") not in (None, *people) for row in job.rows) or _unknown_people(
                job
            ):  # someone left
                mark_failed(db, job, "Uma pessoa do arquivo deixou de ser da família. Comece de novo.")
                return
            kept = [row for row in job.rows if row["row"] not in skipped_rows]
            # A merchant column counts only while the family has merchants on; a name the family has is reused, a new one
            # is created
            merchants = {}
            if get_family(db, job.family_id).merchants_enabled:
                first_spelling: dict[str, str] = {}
                for row in kept:
                    if row.get("merchant"):
                        first_spelling.setdefault(name_key(row["merchant"]), row["merchant"])
                merchants = _merchant_ids(db, job.family_id, set(first_spelling.values()))
            add_transactions(
                db,
                job.family_id,
                job.requested_by,
                [
                    {
                        **row,
                        "category_id": resolved[name_key(row["category"])],
                        "merchant_id": merchants.get(name_key(row["merchant"])) if row.get("merchant") else None,
                    }
                    for row in kept
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

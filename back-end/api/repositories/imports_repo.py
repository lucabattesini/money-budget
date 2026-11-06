from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from schemas.tables import ImportJobDB, TransactionDB

KEEP_JOBS_FOR = timedelta(days=1)
# A job that has been queued or running for longer than this is stuck (for example the server restarted)
STUCK_AFTER = timedelta(minutes=5)

# All times come from the database clock, so the app and the database can never disagree about "now".


def _last_touched():
    """When the person last did something with the job: confirmed it, or else uploaded it."""
    return func.coalesce(ImportJobDB.queued_at, ImportJobDB.created_at)


def create_import_job(
    db: Session, family_id: UUID, user_id: UUID, filename: str, columns: list[str], raw_rows: list
) -> ImportJobDB:
    """The file as it was read, before the person says which column is which."""
    job = ImportJobDB(
        family_id=family_id,
        requested_by=user_id,
        status="staged",
        filename=filename[:255],
        columns=columns,
        raw_rows=raw_rows,
        category_map={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_import_job(
    db: Session, job_id: UUID, family_id: UUID | None = None, user_id: UUID | None = None
) -> ImportJobDB | None:
    """The job, or None. With `family_id` and `user_id` it only finds jobs of that family uploaded by that person."""
    query = db.query(ImportJobDB).filter_by(id=job_id)
    if family_id is not None:
        query = query.filter_by(family_id=family_id)
    if user_id is not None:
        query = query.filter_by(requested_by=user_id)
    return query.first()


def has_active_import_job(db: Session, family_id: UUID) -> bool:
    """True if the family has an import that is waiting or running."""
    return (
        db.query(ImportJobDB.id)
        .filter(ImportJobDB.family_id == family_id, ImportJobDB.status.in_(("queued", "running")))
        .first()
        is not None
    )


def delete_staged_jobs_of(db: Session, family_id: UUID, user_id: UUID) -> None:
    """A person has one file in preparation at a time: uploading another throws the previous one away."""
    db.query(ImportJobDB).filter_by(family_id=family_id, requested_by=user_id, status="staged").delete(
        synchronize_session=False
    )
    db.commit()


def delete_job(db: Session, job: ImportJobDB) -> None:
    db.delete(job)
    db.commit()


def set_checked_rows(db: Session, job: ImportJobDB, column_map: dict, rows: list[dict]) -> None:
    """The columns were matched and every row is fine. The choices about categories stay: they are about names, and a
    name that is no longer in the file is simply never looked at."""
    job.column_map = column_map
    job.rows = rows
    job.total_rows = len(rows)
    job.category_map = job.category_map or {}
    db.commit()


def set_rows(db: Session, job: ImportJobDB, rows: list[dict]) -> None:
    job.rows = rows  # a new list, so the change is noticed
    db.commit()


def set_category_map(db: Session, job: ImportJobDB, category_map: dict) -> None:
    job.category_map = category_map  # a new dict, so the change is noticed
    db.commit()


def mark_queued(db: Session, job: ImportJobDB) -> None:
    job.status = "queued"
    job.queued_at = func.now()
    db.commit()


def mark_running(db: Session, job: ImportJobDB) -> None:
    job.status = "running"
    db.commit()


def mark_done(db: Session, job: ImportJobDB, imported: int, skipped: list[dict]) -> None:
    """Also commits whatever was added to the session before (the imported transactions)."""
    job.status = "done"
    job.imported_count = imported
    job.skipped = skipped
    job.rows = None  # not needed any more
    job.raw_rows = None
    job.finished_at = func.now()
    db.commit()


def mark_failed(db: Session, job: ImportJobDB, error: str) -> None:
    job.status = "failed"
    job.error = error[:255]
    job.rows = None
    job.raw_rows = None
    job.finished_at = func.now()
    db.commit()


def fail_stuck_import_jobs(db: Session, family_id: UUID, error: str) -> None:
    """Mark the family's jobs that have been queued or running for too long as failed."""
    db.query(ImportJobDB).filter(
        ImportJobDB.family_id == family_id,
        ImportJobDB.status.in_(("queued", "running")),
        ImportJobDB.queued_at < func.now() - STUCK_AFTER,
    ).update(
        {"status": "failed", "error": error, "rows": None, "raw_rows": None, "finished_at": func.now()},
        synchronize_session=False,
    )
    db.commit()


def delete_old_import_jobs(db: Session) -> None:
    """Throw away every job (and its rows) that is older than a day, whoever it belongs to. A job counts from the moment
    it was confirmed, if it was: one that waited a long time for the person must not vanish while it runs."""
    db.query(ImportJobDB).filter(_last_touched() < func.now() - KEEP_JOBS_FOR).delete(synchronize_session=False)
    db.commit()


def is_expired(job: ImportJobDB, db: Session) -> bool:
    """True if the job is older than the time jobs are kept (asked of the database clock), counted as above."""
    return (
        db.query(ImportJobDB.id).filter(ImportJobDB.id == job.id, _last_touched() < func.now() - KEEP_JOBS_FOR).first()
        is not None
    )


def existing_transaction_keys(db: Session, family_id: UUID, first: date, last: date) -> set[tuple]:
    """(day, description, value in cents, category id, type) of the family's transactions from `first` to `last`."""
    rows = (
        db.query(
            TransactionDB.transactioned_at,
            TransactionDB.label,
            TransactionDB.value,
            TransactionDB.category_id,
            TransactionDB.type,
        )
        .filter(
            TransactionDB.family_id == family_id,
            TransactionDB.transactioned_at >= datetime.combine(first, time.min),
            TransactionDB.transactioned_at < datetime.combine(last + timedelta(days=1), time.min),
        )
        .all()
    )
    return {(r.transactioned_at.date(), (r.label or "").strip(), r.value, str(r.category_id), r.type) for r in rows}


def add_transactions(db: Session, family_id: UUID, user_id: UUID, items: list[dict]) -> None:
    """Add the transactions to the session. The caller commits, together with marking the job done, so either
    everything is saved or nothing is."""
    db.add_all(
        TransactionDB(
            family_id=family_id,
            merchant_id=item.get("merchant_id"),
            # the file may name a person; else whoever imports. The job's JSON keeps ids as text.
            user_id=UUID(item["user_id"]) if item.get("user_id") else user_id,
            label=item["label"],
            value=item["value"],
            type=item["type"],
            category_id=UUID(item["category_id"]),
            transactioned_at=datetime.combine(date.fromisoformat(item["date"]), time(12, 0)),
        )
        for item in items
    )

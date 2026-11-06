from datetime import timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, defer

from schemas.tables import ExportJobDB

KEEP_FILES_FOR = timedelta(days=1)
# A job that has been queued or running for longer than this is stuck (for example the server restarted)
STUCK_AFTER = timedelta(minutes=5)

# All times come from the database clock, so the app and the database can never disagree about "now".


def create_export_job(db: Session, family_id: UUID, user_id: UUID, file_format: str) -> ExportJobDB:
    job = ExportJobDB(family_id=family_id, requested_by=user_id, format=file_format, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_export_job(
    db: Session, job_id: UUID, family_id: UUID | None = None, user_id: UUID | None = None, with_file: bool = False
) -> ExportJobDB | None:
    """The job, or None. With `family_id` and `user_id` it only finds jobs of that family asked for by that person.

    The finished file can be large, so it is only loaded when `with_file` is set.
    """
    query = db.query(ExportJobDB).filter_by(id=job_id)
    if not with_file:
        query = query.options(defer(ExportJobDB.content))
    if family_id is not None:
        query = query.filter_by(family_id=family_id)
    if user_id is not None:
        query = query.filter_by(requested_by=user_id)
    return query.first()


def has_active_export_job(db: Session, family_id: UUID) -> bool:
    """True if the family has an export that is waiting or being built."""
    return (
        db.query(ExportJobDB.id)
        .filter(ExportJobDB.family_id == family_id, ExportJobDB.status.in_(("queued", "running")))
        .first()
        is not None
    )


def mark_running(db: Session, job: ExportJobDB) -> None:
    job.status = "running"
    db.commit()


def mark_done(db: Session, job: ExportJobDB, filename: str, media_type: str, content: bytes) -> None:
    job.status = "done"
    job.filename = filename
    job.media_type = media_type
    job.content = content
    job.finished_at = func.now()
    db.commit()


def mark_failed(db: Session, job: ExportJobDB, error: str) -> None:
    job.status = "failed"
    job.error = error[:255]
    job.finished_at = func.now()
    db.commit()


def fail_stuck_export_jobs(db: Session, family_id: UUID, error: str) -> None:
    """Mark the family's jobs that have been queued or running for too long as failed."""
    db.query(ExportJobDB).filter(
        ExportJobDB.family_id == family_id,
        ExportJobDB.status.in_(("queued", "running")),
        ExportJobDB.created_at < func.now() - STUCK_AFTER,
    ).update({"status": "failed", "error": error, "finished_at": func.now()}, synchronize_session=False)
    db.commit()


def delete_old_export_jobs(db: Session) -> None:
    """Throw away every job (and its file) that is older than a day, whoever it belongs to."""
    db.query(ExportJobDB).filter(ExportJobDB.created_at < func.now() - KEEP_FILES_FOR).delete(synchronize_session=False)
    db.commit()


def is_expired(job: ExportJobDB, db: Session) -> bool:
    """True if the job is older than the time files are kept (asked of the database clock)."""
    return db.query(func.now() - KEEP_FILES_FOR > job.created_at).scalar() is True

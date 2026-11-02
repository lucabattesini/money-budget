from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, defer

from schemas.tables import ExportJobDB

KEEP_FILES_FOR = timedelta(days=1)
# A job that has been queued or running for longer than this is stuck (for example the server restarted)
STUCK_AFTER = timedelta(minutes=5)

# All times come from the database clock, so the app and the database can never disagree about "now".


def create_export_job(db: Session, user_id: int, file_format: str) -> ExportJobDB:
    job = ExportJobDB(user_id=user_id, format=file_format, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_export_job(db: Session, job_id: int, user_id: int | None = None, with_file: bool = False) -> ExportJobDB | None:
    """The job, or None. With `user_id` it only finds the user's own jobs.

    The finished file can be large, so it is only loaded when `with_file` is set.
    """
    query = db.query(ExportJobDB).filter_by(id=job_id)
    if not with_file:
        query = query.options(defer(ExportJobDB.content))
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def has_active_export_job(db: Session, user_id: int) -> bool:
    """True if the user has an export that is waiting or being built."""
    return (
        db.query(ExportJobDB.id)
        .filter(ExportJobDB.user_id == user_id, ExportJobDB.status.in_(("queued", "running")))
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


def fail_stuck_export_jobs(db: Session, user_id: int, error: str) -> None:
    """Mark the user's jobs that have been queued or running for too long as failed."""
    db.query(ExportJobDB).filter(
        ExportJobDB.user_id == user_id,
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

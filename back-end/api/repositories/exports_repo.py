from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from schemas.tables import ExportJobDB

KEEP_FILES_FOR = timedelta(days=1)


def create_export_job(db: Session, user_id: int, file_format: str) -> ExportJobDB:
    job = ExportJobDB(user_id=user_id, format=file_format, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_export_job(db: Session, job_id: int, user_id: int | None = None) -> ExportJobDB | None:
    """The job, or None. With `user_id` it only finds the user's own jobs."""
    query = db.query(ExportJobDB).filter_by(id=job_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def mark_running(db: Session, job: ExportJobDB) -> None:
    job.status = "running"
    db.commit()


def mark_done(db: Session, job: ExportJobDB, filename: str, media_type: str, content: bytes) -> None:
    job.status = "done"
    job.filename = filename
    job.media_type = media_type
    job.content = content
    job.finished_at = datetime.now()
    db.commit()


def mark_failed(db: Session, job: ExportJobDB, error: str) -> None:
    job.status = "failed"
    job.error = error[:255]
    job.finished_at = datetime.now()
    db.commit()


def delete_old_export_jobs(db: Session, user_id: int) -> None:
    """Throw away the user's jobs (and their files) that are older than a day."""
    db.query(ExportJobDB).filter(
        ExportJobDB.user_id == user_id, ExportJobDB.created_at < datetime.now() - KEEP_FILES_FOR
    ).delete()
    db.commit()

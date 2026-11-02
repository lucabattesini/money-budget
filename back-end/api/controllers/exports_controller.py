import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.exports_repo import (
    create_export_job,
    delete_old_export_jobs,
    fail_stuck_export_jobs,
    get_export_job,
    has_active_export_job,
    is_expired,
    mark_done,
    mark_failed,
    mark_running,
)
from api.repositories.transactions_repo import list_all_transactions
from api.services.export_service import export_transactions
from db.connection import session_scope
from schemas.tables import ExportJobDB

logger = logging.getLogger(__name__)

FAILED_MESSAGE = "Não foi possível gerar o arquivo."
STUCK_MESSAGE = "A exportação demorou demais e foi cancelada."


def enqueue_export(db: Session, user_id: int, file_format: str) -> ExportJobDB:
    """Record the request. The file is built later by run_export_job.

    One export at a time per user: every job loads all their transactions and keeps a copy of the file.
    """
    delete_old_export_jobs(db)
    fail_stuck_export_jobs(db, user_id, STUCK_MESSAGE)
    if has_active_export_job(db, user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já tem uma exportação em andamento.")
    return create_export_job(db, user_id, file_format)


def get_export(db: Session, job_id: int, user_id: int, with_file: bool = False) -> ExportJobDB:
    job = get_export_job(db, job_id, user_id, with_file=with_file)
    # Missing, someone else's and expired all look the same, so ids of other users are not revealed
    if job is None or is_expired(job, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if job.status in ("queued", "running"):
        fail_stuck_export_jobs(db, user_id, STUCK_MESSAGE)
        db.refresh(job)
    return job


def get_export_file(db: Session, job_id: int, user_id: int) -> ExportJobDB:
    job = get_export(db, job_id, user_id, with_file=True)
    if job.status != "done":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Export is {job.status}, not ready")
    return job


def run_export_job(job_id: int) -> None:
    """Build the file for a queued job. Runs in the background, after the response was sent."""
    with session_scope() as db:
        job = get_export_job(db, job_id)
        if job is None:
            return
        try:
            mark_running(db, job)
            document = export_transactions(list_all_transactions(db, job.user_id), job.format)
            filename = f"transacoes-{date.today().isoformat()}.{document.extension}"
            mark_done(db, job, filename, document.media_type, document.content)
        except Exception:
            logger.exception("Export job %s failed", job_id)
            try:
                db.rollback()
                mark_failed(db, job, FAILED_MESSAGE)
            except Exception:
                # Even recording the failure failed (database down?). The job is reaped as stuck later.
                logger.exception("Could not mark export job %s as failed", job_id)

import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.exports_repo import (
    create_export_job,
    delete_old_export_jobs,
    get_export_job,
    mark_done,
    mark_failed,
    mark_running,
)
from api.repositories.transactions_repo import list_all_transactions
from api.services.export_service import export_transactions
from db.connection import session_scope
from schemas.tables import ExportJobDB

logger = logging.getLogger(__name__)


def enqueue_export(db: Session, user_id: int, file_format: str) -> ExportJobDB:
    """Record the request. The file is built later by run_export_job."""
    delete_old_export_jobs(db, user_id)
    return create_export_job(db, user_id, file_format)


def get_export(db: Session, job_id: int, user_id: int) -> ExportJobDB:
    job = get_export_job(db, job_id, user_id)
    if job is None:  # missing and someone else's look the same, so ids of other users are not revealed
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return job


def get_export_file(db: Session, job_id: int, user_id: int) -> ExportJobDB:
    job = get_export(db, job_id, user_id)
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
            db.rollback()
            mark_failed(db, job, "Não foi possível gerar o arquivo.")

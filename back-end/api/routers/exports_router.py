from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id, get_current_user_id
from api.controllers.exports_controller import enqueue_export, get_export, get_export_file, run_export_job
from db.connection import get_db
from schemas.tables_schemas import ExportJobCreate, ExportJobOut

router = APIRouter(prefix="/exports", tags=["exports"], responses={404: {"description": "Not found"}})


def _out(job) -> dict:
    return jsonable_encoder(ExportJobOut.model_validate(job))


@router.post("")
async def create_export_router(
    params: ExportJobCreate,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Queue an export. Answers at once; poll GET /exports/{id} until it is done."""
    job = enqueue_export(db, family_id, user_id, params.format)
    background_tasks.add_task(run_export_job, job.id)
    return JSONResponse(content={"data": _out(job)}, status_code=status.HTTP_202_ACCEPTED)


@router.get("/{job_id}")
async def get_export_router(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    return JSONResponse(
        content={"data": _out(get_export(db, job_id, family_id, user_id))}, status_code=status.HTTP_200_OK
    )


@router.get("/{job_id}/file")
async def get_export_file_router(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    job = get_export_file(db, job_id, family_id, user_id)
    return Response(
        content=job.content,
        media_type=job.media_type,
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
    )

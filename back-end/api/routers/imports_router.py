from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id, get_current_user_id
from api.controllers.imports_controller import (
    ImportRejected,
    cancel_import,
    choose_categories,
    describe_job,
    get_import,
    run_import_job,
    stage_import,
    start_import,
)
from api.gateways.documents import MAX_FILE_BYTES
from db.connection import get_db
from schemas.tables_schemas import ImportCategoriesChoice

router = APIRouter(prefix="/imports", tags=["imports"], responses={404: {"description": "Not found"}})


def _data(db: Session, job) -> dict:
    return {"data": jsonable_encoder(describe_job(db, job))}


@router.post("")
async def upload_import_router(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 1: check the whole file. Answers 422 with the list of problems if anything is wrong (nothing is kept)."""
    content = await file.read(MAX_FILE_BYTES + 1)  # never more than the limit in memory
    try:
        job = stage_import(db, family_id, user_id, file.filename or "", content)
    except ImportRejected as rejected:
        return JSONResponse(
            content={"detail": rejected.message, "problems": rejected.problems, "problems_total": rejected.total},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return JSONResponse(content={"data": jsonable_encoder(job)}, status_code=status.HTTP_201_CREATED)


@router.get("/{job_id}")
async def get_import_router(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    return JSONResponse(content=_data(db, get_import(db, job_id, family_id, user_id)), status_code=status.HTTP_200_OK)


@router.put("/{job_id}/categories")
async def choose_import_categories_router(
    job_id: int,
    choice: ImportCategoriesChoice,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 2: which category of the family each unknown name in the file stands for."""
    job = choose_categories(db, job_id, family_id, user_id, choice.mapping)
    return JSONResponse(content=_data(db, job), status_code=status.HTTP_200_OK)


@router.post("/{job_id}/start")
async def start_import_router(
    job_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 3: queue the import. Answers at once; poll GET /imports/{id} until it is done."""
    job = start_import(db, job_id, family_id, user_id)
    background_tasks.add_task(run_import_job, job.id)
    return JSONResponse(content=_data(db, job), status_code=status.HTTP_202_ACCEPTED)


@router.delete("/{job_id}")
async def cancel_import_router(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Give up before starting: throws the checked file away."""
    cancel_import(db, job_id, family_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id, get_current_user_id
from api.controllers.imports_controller import (
    ImportRejected,
    cancel_import,
    choose_categories,
    choose_people,
    describe_job,
    get_import,
    match_columns,
    run_import_job,
    stage_import,
    start_import,
)
from api.gateways.documents import MAX_FILE_BYTES
from db.connection import get_db
from schemas.tables_schemas import ImportCategoriesChoice, ImportColumnsChoice, ImportPeopleChoice

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
    """Step 1: read the file. The answer has its columns, a suggestion of which is which and a few rows to recognise them."""
    content = await file.read(MAX_FILE_BYTES + 1)  # never more than the limit in memory
    job = stage_import(db, family_id, user_id, file.filename or "", content)
    return JSONResponse(content={"data": jsonable_encoder(job)}, status_code=status.HTTP_201_CREATED)


@router.get("/{job_id}")
async def get_import_router(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    return JSONResponse(content=_data(db, get_import(db, job_id, family_id, user_id)), status_code=status.HTTP_200_OK)


@router.put("/{job_id}/columns")
async def match_import_columns_router(
    job_id: int,
    choice: ImportColumnsChoice,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 2: which column of the file is which field. Checks the whole file: answers 422 with the list of problems if
    any row is wrong (nothing is kept)."""
    try:
        job, date_order = match_columns(
            db, job_id, family_id, user_id, choice.mapping, choice.date_order, choice.amount_style, choice.sign
        )
    except ImportRejected as rejected:
        return JSONResponse(
            content={"detail": rejected.message, "problems": rejected.problems, "problems_total": rejected.total},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    content = _data(db, job)
    # How the file was read, for the person to confirm
    content["data"].update(date_order=date_order, amount_style=choice.amount_style, sign=choice.sign)
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)


@router.put("/{job_id}/categories")
async def choose_import_categories_router(
    job_id: int,
    choice: ImportCategoriesChoice,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 3: which category of the family each unknown name in the file stands for."""
    job = choose_categories(db, job_id, family_id, user_id, choice.mapping)
    return JSONResponse(content=_data(db, job), status_code=status.HTTP_200_OK)


@router.put("/{job_id}/people")
async def choose_import_people_router(
    job_id: int,
    choice: ImportPeopleChoice,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 3: which member of the family each name of the Pessoa column that matched nobody stands for."""
    job = choose_people(db, job_id, family_id, user_id, choice.mapping)
    return JSONResponse(content=_data(db, job), status_code=status.HTTP_200_OK)


@router.post("/{job_id}/start")
async def start_import_router(
    job_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """Step 4: queue the import. Answers at once; poll GET /imports/{id} until it is done."""
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

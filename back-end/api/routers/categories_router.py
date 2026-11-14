from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id
from api.controllers.categories_controller import (
    create_family_category,
    delete_family_category,
    get_all_categories,
    get_all_groups,
    update_family_category,
)
from db.connection import get_db
from schemas.tables_schemas import CategoryCreate, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"], responses={404: {"description": "Not found"}})


# Both spellings: the web app asks for "/categories". Once POST "/categories" exists, that path stops being
# redirected to "/categories/" and a GET on it would answer 405.
@router.get("")
@router.get("/")
def get_all_categories_router(family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)):
    categories = get_all_categories(db, family_id)
    json_result = jsonable_encoder(categories)
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.get("/groups")
def get_all_groups_router(family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)):
    """The groups the categories are listed under: a fixed set, the same for every family."""
    return JSONResponse(content={"data": jsonable_encoder(get_all_groups(db))}, status_code=status.HTTP_200_OK)


@router.post("")
def create_category_router(
    params: CategoryCreate, family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    created = create_family_category(db, family_id, params.name, params.group_id)
    return JSONResponse(content={"data": jsonable_encoder(created)}, status_code=status.HTTP_201_CREATED)


@router.patch("/{category_id}")
def update_category_router(
    category_id: UUID,
    params: CategoryUpdate,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    updated = update_family_category(db, family_id, category_id, params.name, params.group_id)
    return JSONResponse(content={"data": jsonable_encoder(updated)}, status_code=status.HTTP_200_OK)


@router.delete("/{category_id}")
def delete_category_router(
    category_id: UUID, family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    return JSONResponse(
        content={"data": delete_family_category(db, family_id, category_id)}, status_code=status.HTTP_200_OK
    )

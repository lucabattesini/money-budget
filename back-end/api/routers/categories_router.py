from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id
from api.controllers.categories_controller import get_all_categories, get_all_groups
from db.connection import get_db

router = APIRouter(prefix="/categories", tags=["categories"], responses={404: {"description": "Not found"}})


@router.get("/")
async def get_all_categories_router(family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    categories = get_all_categories(db, family_id)
    json_result = jsonable_encoder(categories)
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.get("/groups")
async def get_all_groups_router(family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)):
    """The groups the categories are listed under: a fixed set, the same for every family."""
    return JSONResponse(content={"data": jsonable_encoder(get_all_groups(db))}, status_code=status.HTTP_200_OK)

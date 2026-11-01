from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.categories_controller import get_all_categories
from db.connection import get_db

router = APIRouter(prefix="/categories", tags=["categories"], responses={404: {"description": "Not found"}})


@router.get("/")
async def get_all_categories_router(db: Session = Depends(get_db)):
    categories = get_all_categories(db)
    json_result = jsonable_encoder(categories)
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)

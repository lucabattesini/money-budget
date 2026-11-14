from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id
from api.controllers.merchants_controller import (
    create_family_merchant,
    delete_family_merchant,
    list_merchants,
    rename_family_merchant,
)
from db.connection import get_db
from schemas.tables_schemas import MerchantName

router = APIRouter(prefix="/merchants", tags=["merchants"], responses={404: {"description": "Not found"}})


# Both spellings, like /categories: a POST on "/merchants" must not turn a GET into a 405
@router.get("")
@router.get("/")
def list_merchants_router(family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)):
    return JSONResponse(
        content={"data": jsonable_encoder(list_merchants(db, family_id))}, status_code=status.HTTP_200_OK
    )


@router.post("")
def create_merchant_router(
    params: MerchantName, family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    created = create_family_merchant(db, family_id, params.name)
    return JSONResponse(content={"data": jsonable_encoder(created)}, status_code=status.HTTP_201_CREATED)


@router.patch("/{merchant_id}")
def rename_merchant_router(
    merchant_id: UUID,
    params: MerchantName,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    renamed = rename_family_merchant(db, family_id, merchant_id, params.name)
    return JSONResponse(content={"data": jsonable_encoder(renamed)}, status_code=status.HTTP_200_OK)


@router.delete("/{merchant_id}")
def delete_merchant_router(
    merchant_id: UUID, family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    return JSONResponse(
        content={"data": delete_family_merchant(db, family_id, merchant_id)}, status_code=status.HTTP_200_OK
    )

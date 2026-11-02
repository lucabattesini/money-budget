from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id, get_current_user_id
from api.controllers.transactions_controller import (
    create_transaction,
    delete_transaction,
    get_transactions,
    get_transactions_summed_by_category,
    update_transaction,
)
from db.connection import get_db
from schemas.tables_schemas import GetTransactionsParams, Transaction, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"], responses={404: {"description": "Not found"}})


@router.post("/")
async def get_transactions_router(
    transactionsParams: GetTransactionsParams,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions(db, transactionsParams, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/summed-by-category")
async def get_summed_transactions_by_category_router(
    transactionsParams: GetTransactionsParams,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions_summed_by_category(db, transactionsParams, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/create")
async def create_transaction_router(
    params: Transaction,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    family_id: int = Depends(get_current_family_id),
):
    json_result = jsonable_encoder(create_transaction(db, params, family_id, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_201_CREATED)


@router.delete("/{id}")
async def delete_transaction_router(
    id: int,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(delete_transaction(db, id, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_202_ACCEPTED)


@router.put("/{id}")
async def update_transaction_router(
    id: int,
    params: TransactionUpdate,
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(update_transaction(db, id, params, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)

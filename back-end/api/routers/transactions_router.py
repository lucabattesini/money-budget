from fastapi import APIRouter, status, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import Transaction, GetTransactionsParams
from api.controllers.transactions_controller import (
    get_transactions_summed_by_category,
    create_transaction,
    delete_transaction,
    get_transactions,
)
from api.controllers.auth_controller import get_current_user_id
from fastapi import Depends
from sqlalchemy.orm import Session
from db.connection import get_db


router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={404: {"description": "Not found"}}
)



@router.post("/")
async def get_transactions_router(
    transactionsParams: GetTransactionsParams,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions(db, transactionsParams, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/summed-by-category")
async def get_summed_transactions_by_category_router(
    transactionsParams: GetTransactionsParams,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions_summed_by_category(db, transactionsParams, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/create")
async def create_transaction_router(
    params: Transaction,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(create_transaction(db, params, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_201_CREATED)


@router.delete("/{id}")
async def delete_transaction_router(
    id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(delete_transaction(db, id, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_202_ACCEPTED)
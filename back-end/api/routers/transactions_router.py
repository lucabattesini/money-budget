from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id, get_current_user_id
from api.controllers.transactions_controller import (
    bulk_delete_transactions_controller,
    bulk_update_transactions_controller,
    create_transaction,
    delete_transaction,
    get_duplicate_groups,
    get_transactions,
    get_transactions_summed_by_category,
    update_transaction,
)
from db.connection import get_db
from schemas.tables_schemas import (
    DuplicatesParams,
    GetTransactionsParams,
    Transaction,
    TransactionBulkDelete,
    TransactionBulkUpdate,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"], responses={404: {"description": "Not found"}})


# Both spellings: the web app posts to "/transactions", and the web app's own files are served from "/" in production, where
# a missing slash is not redirected (see api/app.py)
@router.post("")
@router.post("/")
async def get_transactions_router(
    transactionsParams: GetTransactionsParams,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions(db, transactionsParams, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/summed-by-category")
async def get_summed_transactions_by_category_router(
    transactionsParams: GetTransactionsParams,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_transactions_summed_by_category(db, transactionsParams, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/create")
async def create_transaction_router(
    params: Transaction,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    family_id: UUID = Depends(get_current_family_id),
):
    json_result = jsonable_encoder(create_transaction(db, params, family_id, user_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_201_CREATED)


@router.post("/bulk-update")
async def bulk_update_transactions_router(
    params: TransactionBulkUpdate,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(bulk_update_transactions_controller(db, params, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/bulk-delete")
async def bulk_delete_transactions_router(
    params: TransactionBulkDelete,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(bulk_delete_transactions_controller(db, params, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.post("/duplicates")
async def duplicate_transactions_router(
    params: DuplicatesParams,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(get_duplicate_groups(db, params, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)


@router.delete("/{id}")
async def delete_transaction_router(
    id: UUID,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(delete_transaction(db, id, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_202_ACCEPTED)


@router.put("/{id}")
async def update_transaction_router(
    id: UUID,
    params: TransactionUpdate,
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    json_result = jsonable_encoder(update_transaction(db, id, params, family_id))
    return JSONResponse(content={"data": json_result}, status_code=status.HTTP_200_OK)

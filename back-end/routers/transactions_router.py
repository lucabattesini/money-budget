from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import Transaction, GetTransactionsParams
from controllers.transactions_controller import get_transactions_summed_by_category, create_transaction, delete_transaction, get_transactions

router = APIRouter(
    prefix="/transactions",
    tags=["transactions "],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def get_transactions_router(transactions: GetTransactionsParams):
    json_result = jsonable_encoder(get_transactions(transactions))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.get("/summed-by-category")
async def get_summed_transactions_by_category_router():
    json_result = jsonable_encoder(get_transactions_summed_by_category())
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.post("/create")
async def create_transaction_router(transaction: Transaction):
    json_result = jsonable_encoder(create_transaction(transaction))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_201_CREATED
    )

@router.delete("/{id}")
async def delete_transaction_router(id):
    json_result = jsonable_encoder(delete_transaction(id))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_202_ACCEPTED
    )
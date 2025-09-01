from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import Transaction
from controllers.transactions_controller import get_all_transactions, get_added_transactions_by_category, create_transaction

router = APIRouter(
    prefix="/transactions",
    tags=["transactions "],
    responses={404: {"description": "Not found"}}
)

@router.get("/")
async def get_all_transactions_router():
    transactions = get_all_transactions()
    json_result = jsonable_encoder(transactions)
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.get("/summed-by-category")
async def get_summed_transactions_by_category_router():
    json_result = jsonable_encoder(get_added_transactions_by_category())
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.post("/")
async def create_transaction_router(transaction: Transaction):
    transaction_created = create_transaction(transaction)
    json_result = jsonable_encoder(transaction_created)
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_201_CREATED
    )
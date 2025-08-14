from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import Transaction
from controllers.expenses_controller import report_transaction_ctrl, get_all_transactions_ctrl, get_added_transactions_by_category_ctrl

router = APIRouter(
    prefix="/report-expense",
    tags=["report-expense"],
    responses={404: {"description": "Not found"}}
)
 
@router.get("/")
async def get_all_transactions_router():
    transactions = get_all_transactions_ctrl()
    json_result = jsonable_encoder(transactions)
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.get("/added-by-category")
async def get_added_transactions_by_category_router():
    json_result = jsonable_encoder(get_added_transactions_by_category_ctrl())
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.post("/")
async def report_transaction_router(transaction: Transaction):
    transaction_created = report_transaction_ctrl(transaction.label, transaction.value, transaction.category)
    json_result = jsonable_encoder(transaction_created)
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_201_CREATED
    )
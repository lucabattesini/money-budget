from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import Transaction
from controllers.expenses_controller import report_transaction_ctrl, get_all_transactions_ctrl, get_transactions_by_time_ctrl

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

@router.get("/time-filtered/{time}")
async def get_transactions_by_time(time):
    filtered_transactions = get_transactions_by_time_ctrl(time)
    json_result = jsonable_encoder(filtered_transactions)
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.post("/")
async def report_transaction_router(transaction: Transaction):
    report_transaction_ctrl(transaction.label, transaction.value, transaction.category)
    
    return JSONResponse(
        content={"message": "Transaction saved succesfully"},
        status_code=status.HTTP_201_CREATED
    )
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.tables import Transactions
from controllers.expenses_controller import report_transaction_ctrl

router = APIRouter(
    prefix="/report-expense",
    tags=["report-expense"],
    responses={404: {"description": "Not found"}}
)

@router.put("/")
async def report_transaction_router(transaction: Transactions):
    report_transaction_ctrl(transaction.label, transaction.value, transaction.category)
    
    return JSONResponse(
        content={"message": "Transaction saved succesfully"},
        status_code=status.HTTP_201_CREATED
    )
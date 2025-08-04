from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.tables_schemas import Transaction
from controllers.expenses_controller import report_transaction_ctrl

router = APIRouter(
    prefix="/report-expense",
    tags=["report-expense"],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def report_transaction_router(transaction: Transaction):
    report_transaction_ctrl(transaction.label, transaction.value, transaction.category)
    
    return JSONResponse(
        content={"message": "Transaction saved succesfully"},
        status_code=status.HTTP_201_CREATED
    )
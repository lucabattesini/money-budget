from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.tables import Transactions

router = APIRouter(
    prefix="/report-expense",
    tags=["report-expense"],
    responses={404: {"description": "Not found"}}
)

@router.put("/")
async def update_data_values(transaction: Transactions):
    return
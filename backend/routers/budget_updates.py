from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.profile_schema import UserDefaultBudget

router = APIRouter(
    prefix="/update-budget",
    tags=["update-budget"],
    responses={404: {"description": "Not found"}}
)

@router.put("/{operation}")
async def update_data_values(data: UserDefaultBudget, operation):
    return
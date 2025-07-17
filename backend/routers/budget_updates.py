from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/update-budget",
    tags=["update-budget"],
    responses={404: {"description": "Not found"}}
)

@router.put("/")
async def update_data_values():
    return
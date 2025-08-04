from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from controllers.categories_controller import organize_categories_ctrl

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
    responses={404: {"description": "Not found"}}
)

@router.get("/")
async def get_all_categories_router():
    categories = organize_categories_ctrl()
    return JSONResponse(
        content={"data": categories},
        status_code=status.HTTP_200_OK
    )
from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from api.controllers.users_controller import get_user_by_id_ctrl
from api.controllers.auth_controller import get_current_user_id
from schemas.tables_schemas import UserResponse

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)




@router.get("/me", response_model=UserResponse)
async def get_me(user_id: int = Depends(get_current_user_id)):
    """Return the currently authenticated user based on the JWT."""
    user = get_user_by_id_ctrl(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse(
        content={"data": jsonable_encoder(user)},
        status_code=status.HTTP_200_OK
    )
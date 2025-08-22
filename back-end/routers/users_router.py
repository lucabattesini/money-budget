from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import User
from controllers.users_controller import create_user_ctrl

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)

@router.post("/create-user")
async def create_user(user: User):
    json_result = jsonable_encoder(create_user_ctrl(user.name, user.email, user.password))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_201_CREATED
    )
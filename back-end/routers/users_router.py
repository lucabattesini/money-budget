from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from schemas.tables_schemas import User
from controllers.users_controller import create_user_ctrl, user_login_ctrl, get_all_users
 
router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)

@router.get("/")
async def get_all_users_router():
    json_result = jsonable_encoder(get_all_users())
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_200_OK
    )

@router.post("/create-user")
async def create_user(user: User):
    json_result = jsonable_encoder(create_user_ctrl(user))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_201_CREATED
    )

@router.post("/user-login")
async def login(user: User):
    json_result = jsonable_encoder(user_login_ctrl(user.email, user.password))
    return JSONResponse(
        content={"data": json_result},
        status_code=status.HTTP_202_ACCEPTED
    )
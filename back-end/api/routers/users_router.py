from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_user_id
from api.controllers.users_controller import get_user_by_id_ctrl, update_user_phone_ctrl
from db.connection import get_db
from schemas.tables_schemas import UserResponse, UserUpdatePhone

router = APIRouter(prefix="/user", tags=["user"], responses={404: {"description": "Not found"}})


@router.get("/me", response_model=UserResponse)
def get_me(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Return the currently authenticated user based on the JWT."""
    user = get_user_by_id_ctrl(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse(content={"data": jsonable_encoder(user)}, status_code=status.HTTP_200_OK)


@router.patch("/me/phone", response_model=UserResponse)
def update_phone(
    payload: UserUpdatePhone,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = update_user_phone_ctrl(db, user_id, payload.whatsapp_phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse(content={"data": jsonable_encoder(user)}, status_code=status.HTTP_200_OK)

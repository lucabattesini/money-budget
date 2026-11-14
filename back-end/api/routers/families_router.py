from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_user_id
from api.controllers.families_controller import (
    cancel_family_invite,
    change_family_settings,
    create_family_invite,
    get_my_family,
    go_back_to_previous_family,
    join_with_code,
    list_family_invites,
)
from api.controllers.users_controller import get_user_by_id_ctrl
from db.connection import get_db
from schemas.tables_schemas import FamilySettings, JoinFamily

router = APIRouter(prefix="/families", tags=["families"], responses={404: {"description": "Not found"}})


def _current_user(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = get_user_by_id_ctrl(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def _ok(data, code=status.HTTP_200_OK):
    return JSONResponse(content={"data": jsonable_encoder(data)}, status_code=code)


@router.get("/me")
def get_my_family_router(user=Depends(_current_user), db: Session = Depends(get_db)):
    return _ok(get_my_family(db, user))


@router.patch("/me/settings")
def change_settings_router(settings: FamilySettings, user=Depends(_current_user), db: Session = Depends(get_db)):
    """Change the family's currency and/or language. Any member may; a field left out keeps its value."""
    return _ok(change_family_settings(db, user, settings))


@router.post("/invites")
def create_invite_router(user=Depends(_current_user), db: Session = Depends(get_db)):
    return _ok(create_family_invite(db, user), status.HTTP_201_CREATED)


@router.get("/invites")
def list_invites_router(user=Depends(_current_user), db: Session = Depends(get_db)):
    return _ok(list_family_invites(db, user))


@router.delete("/invites/{invite_id}")
def cancel_invite_router(invite_id: UUID, user=Depends(_current_user), db: Session = Depends(get_db)):
    return _ok(cancel_family_invite(db, user, invite_id))


@router.post("/join")
def join_family_router(params: JoinFamily, user=Depends(_current_user), db: Session = Depends(get_db)):
    return _ok(join_with_code(db, user, params.code, params.bring_data))


@router.post("/rollback")
def go_back_router(user=Depends(_current_user), db: Session = Depends(get_db)):
    """Go back to the family left behind when joining another one with "start empty" (kept for 30 days)."""
    return _ok(go_back_to_previous_family(db, user))

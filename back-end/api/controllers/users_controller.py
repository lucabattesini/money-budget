import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.users_repo import (
    PhoneInUseError,
    get_user_by_google_id_repo,
    get_user_by_id_repo,
    update_user_phone_repo,
    upsert_user_repo,
)


def normalize_phone(phone: str | None) -> str | None:
    """Keep only the digits ("+55 (11) 99999-9999" -> "5511999999999"), the way WhatsApp sends numbers.

    Empty or None means "no number". Raises 422 when what is left is not a plausible number (8 to 15 digits).
    """
    if phone is None:
        return None
    digits = re.sub(r"\D", "", phone)
    if not phone.strip():
        return None
    if not 8 <= len(digits) <= 15:
        raise HTTPException(status_code=422, detail="Invalid phone number")
    return digits


def _phone_taken() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This phone number is already in use")


def upsert_user_ctrl(db: Session, google_id, name, email, picture=None, whatsapp_phone=None):
    """Create or update a user after Google OAuth login."""
    try:
        return upsert_user_repo(db, google_id, name, email, picture, normalize_phone(whatsapp_phone))
    except PhoneInUseError:
        raise _phone_taken()


def get_user_by_google_id_ctrl(db: Session, google_id):
    return get_user_by_google_id_repo(db, google_id)


def get_user_by_id_ctrl(db: Session, user_id: UUID):
    return get_user_by_id_repo(db, user_id)


def update_user_phone_ctrl(db: Session, user_id: UUID, whatsapp_phone: str):
    try:
        return update_user_phone_repo(db, user_id, normalize_phone(whatsapp_phone))
    except PhoneInUseError:
        raise _phone_taken()

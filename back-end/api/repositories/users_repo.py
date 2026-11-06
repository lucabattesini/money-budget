import re
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schemas.tables import Families, Users

PHONE_CONSTRAINT = "uq_users_whatsapp_phone"


class PhoneInUseError(Exception):
    """The WhatsApp number already belongs to another account."""


def _commit(db: Session):
    """Commit; a clash on the WhatsApp number becomes PhoneInUseError, anything else is re-raised."""
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if PHONE_CONSTRAINT in str(e.orig):
            raise PhoneInUseError() from e
        raise
    except Exception:
        db.rollback()
        raise


def upsert_user_repo(
    db: Session, google_id: str, name: str, email: str, picture: str = None, whatsapp_phone: str = None
):
    """Insert a new user or update name/picture/last_login if they already exist."""
    now = datetime.now()
    user = db.query(Users).filter(Users.google_id == google_id).first()

    if user:
        user.name = name
        user.picture = picture
        user.last_login = now
        if whatsapp_phone:
            user.whatsapp_phone = whatsapp_phone
    else:
        family = Families()  # everyone starts in a family of their own
        db.add(family)
        db.flush()
        user = Users(
            family_id=family.id,
            google_id=google_id,
            name=name,
            email=email,
            picture=picture,
            whatsapp_phone=whatsapp_phone,
            last_login=now,
        )
        db.add(user)

    _commit(db)
    db.refresh(user)
    return user


def get_user_by_google_id_repo(db: Session, google_id: str):
    return db.query(Users).filter(Users.google_id == google_id).first()


def get_user_by_id_repo(db: Session, user_id: UUID):
    return db.query(Users).filter(Users.id == user_id).first()


def get_user_by_whatsapp_phone(db: Session, phone: str):
    # Numbers are stored as digits only, so look them up the same way
    return db.query(Users).filter(Users.whatsapp_phone == re.sub(r"\D", "", phone or "")).first()


def update_user_phone_repo(db: Session, user_id: UUID, whatsapp_phone: str):
    user = db.query(Users).filter(Users.id == user_id).first()
    if user:
        user.whatsapp_phone = whatsapp_phone
        _commit(db)
        db.refresh(user)
    return user

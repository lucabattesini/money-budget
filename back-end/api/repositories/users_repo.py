from datetime import datetime
from sqlalchemy.orm import Session
from schemas.tables import Users

def upsert_user_repo(db: Session, google_id: str, name: str, email: str, picture: str = None, whatsapp_phone: str = None):
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
        user = Users(
            google_id=google_id,
            name=name,
            email=email,
            picture=picture,
            whatsapp_phone=whatsapp_phone,
            last_login=now,
        )
        db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise e

    return user

def get_user_by_google_id_repo(db: Session, google_id: str):
    return db.query(Users).filter(Users.google_id == google_id).first()

def get_user_by_id_repo(db: Session, user_id: int):
    return db.query(Users).filter(Users.id == user_id).first()

def get_user_by_whatsapp_phone(db: Session, phone: str):
    return db.query(Users).filter(Users.whatsapp_phone == phone).first()

def update_user_phone_repo(db: Session, user_id: int, whatsapp_phone: str):
    user = db.query(Users).filter(Users.id == user_id).first()
    if user:
        user.whatsapp_phone = whatsapp_phone
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            raise e
    return user

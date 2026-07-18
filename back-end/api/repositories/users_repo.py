from datetime import datetime
from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Users

db: Session = LocalSession()

def upsert_user_repo(google_id: str, name: str, email: str, picture: str = None):
    """Insert a new user or update name/picture/last_login if they already exist."""
    now = datetime.now()
    user = db.query(Users).filter(Users.google_id == google_id).first()

    if user:
        user.name = name
        user.picture = picture
        user.last_login = now
    else:
        user = Users(
            google_id=google_id,
            name=name,
            email=email,
            picture=picture,
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

def get_user_by_google_id_repo(google_id: str):
    return db.query(Users).filter(Users.google_id == google_id).first()

def get_user_by_id_repo(user_id: int):
    return db.query(Users).filter(Users.id == user_id).first()

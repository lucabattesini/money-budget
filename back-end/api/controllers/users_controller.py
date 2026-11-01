from sqlalchemy.orm import Session
from api.repositories.users_repo import upsert_user_repo, get_user_by_google_id_repo, get_user_by_id_repo, update_user_phone_repo

def upsert_user_ctrl(db: Session, google_id, name, email, picture=None, whatsapp_phone=None):
    """Create or update a user after Google OAuth login."""
    return upsert_user_repo(db, google_id, name, email, picture, whatsapp_phone)

def get_user_by_google_id_ctrl(db: Session, google_id):
    return get_user_by_google_id_repo(db, google_id)

def get_user_by_id_ctrl(db: Session, user_id: int):
    return get_user_by_id_repo(db, user_id)

def update_user_phone_ctrl(db: Session, user_id: int, whatsapp_phone: str):
    return update_user_phone_repo(db, user_id, whatsapp_phone)

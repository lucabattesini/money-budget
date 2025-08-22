from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import Users

def create_user(name, email, password, created_at, updated_at, last_login, is_active):
    db: Session = LocalSession()
    try:
        db.add(Users(name=name, 
                     email=email, 
                     password=password, 
                     created_at=created_at,
                     updated_at=updated_at,
                     last_login=last_login,
                     is_active=is_active
                    ))
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()

    return {
        "name": name,
        "email": email,
        "password": password,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_login": last_login,
        "is_active": is_active
    }
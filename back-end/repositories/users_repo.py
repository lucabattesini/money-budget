from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Users

db: Session = LocalSession()

def create_user_repo(name, email, password, created_at, updated_at, last_login, is_active):
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
  
    return {
        "name": name,
        "email": email,
        "password": password,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_login": last_login,
        "is_active": is_active
    }

def user_login_repo(email, password):
    user = (
        db.query(Users)
        .filter(Users.email == email)
        .filter(Users.password == password)
        .all()
    )
    return user
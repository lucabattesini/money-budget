from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import UsersDB
from schemas.tables_schemas import User
 
db: Session = LocalSession()

def get_all_users():
    return db.query(UsersDB).all()

def create_user_repo(u: User):
    try:
        user = UsersDB(**u.dict())
        db.add(user)
        db.commit()
        return user
    
    except Exception as e:
        db.rollback()
        raise

def user_login_repo(email, password):
    user = (
        db.query(UsersDB)
        .filter(UsersDB.email == email)
        .filter(UsersDB.password == password)
        .all()
    )
    return user
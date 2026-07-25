from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Categories
 
from sqlalchemy import func

db: Session = LocalSession()

def get_all_categories():
    return db.query(Categories).all()

def get_category_by_name(name: str):
    return db.query(Categories).filter(func.lower(Categories.name) == name.lower()).first()
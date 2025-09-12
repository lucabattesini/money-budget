from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Categories
 
db: Session = LocalSession()

def get_all_categories():
    return db.query(Categories).all()
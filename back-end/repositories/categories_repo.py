from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Categories

db: Session = LocalSession()

def get_all_categories_repo():

    categories = db.query(Categories).all()

    return categories
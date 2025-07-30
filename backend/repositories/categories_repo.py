from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Categories

def get_all_categories_repo():
    db : Session = LocalSession

    categories = db.query(Categories).all()

    return categories
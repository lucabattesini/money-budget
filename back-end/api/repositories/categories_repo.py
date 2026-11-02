from sqlalchemy import func
from sqlalchemy.orm import Session

from schemas.tables import Categories


def get_all_categories(db: Session):
    return db.query(Categories).all()


def get_category_by_name(db: Session, name: str):
    return db.query(Categories).filter(func.lower(Categories.name) == name.lower()).first()

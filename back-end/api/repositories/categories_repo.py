from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from schemas.tables import Categories


def _visible(family_id: int):
    """Default categories (no family) plus the family's own."""
    return or_(Categories.family_id.is_(None), Categories.family_id == family_id)


def get_all_categories(db: Session, family_id: int):
    return db.query(Categories).filter(_visible(family_id)).all()


def get_category_by_name(db: Session, name: str, family_id: int):
    # The family's own category wins over a default one with the same name
    return (
        db.query(Categories)
        .filter(_visible(family_id), func.lower(Categories.name) == name.lower())
        .order_by(Categories.family_id.is_(None), Categories.id)
        .first()
    )


def category_visible_to_family(db: Session, category_id: int, family_id: int) -> bool:
    return db.query(Categories.id).filter(Categories.id == category_id, _visible(family_id)).first() is not None

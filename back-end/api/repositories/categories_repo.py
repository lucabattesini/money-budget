from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from schemas.tables import Categories, CategoryGroups


def _visible(family_id: int):
    """Default categories (no family) plus the family's own."""
    return or_(Categories.family_id.is_(None), Categories.family_id == family_id)


def get_all_categories(db: Session, family_id: int):
    """The categories the family can use, each with the name of its group."""
    return (
        db.query(Categories, CategoryGroups.name)
        .join(CategoryGroups, Categories.group_id == CategoryGroups.id)
        .filter(_visible(family_id))
        .order_by(Categories.id)
        .all()
    )


def get_all_groups(db: Session):
    """Every group, in the order they are shown. The same for everyone."""
    return db.query(CategoryGroups).order_by(CategoryGroups.id).all()


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

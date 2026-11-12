from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.repositories.budgets_repo import UNBUDGETED_GROUPS, delete_budgets_of_category
from api.utils.category_names import same_name
from schemas.tables import Categories, CategoryGroups, Families, TransactionDB


def _visible(family_id: UUID):
    """Default categories (no family) plus the family's own."""
    return or_(Categories.family_id.is_(None), Categories.family_id == family_id)


def get_all_categories(db: Session, family_id: UUID):
    """The categories the family can use, each with the name and the place (position) of its group."""
    return (
        db.query(Categories, CategoryGroups.name, CategoryGroups.position)
        .join(CategoryGroups, Categories.group_id == CategoryGroups.id)
        .filter(_visible(family_id))
        .order_by(Categories.name, Categories.id)
        .all()
    )


def get_all_groups(db: Session):
    """Every group, in the order they are shown. The same for everyone."""
    return db.query(CategoryGroups).order_by(CategoryGroups.position, CategoryGroups.id).all()


def get_category_by_name(db: Session, name: str, family_id: UUID):
    """The category with these words as its name, whether or not it starts with an emoji.

    The family's own category wins over a default one with the same name. Compared here and not in SQL, because
    the emoji in front is part of the stored name.
    """
    candidates = (
        db.query(Categories).filter(_visible(family_id)).order_by(Categories.family_id.is_(None), Categories.id)
    )
    return next((category for category in candidates if same_name(category.name, name)), None)


def category_visible_to_family(db: Session, category_id: UUID, family_id: UUID) -> bool:
    return db.query(Categories.id).filter(Categories.id == category_id, _visible(family_id)).first() is not None


def get_family_category(db: Session, family_id: UUID, category_id: UUID) -> Categories | None:
    """One of the family's OWN categories. A default category, another family's and a missing id are all None."""
    return db.query(Categories).filter(Categories.id == category_id, Categories.family_id == family_id).first()


def group_exists(db: Session, group_id: UUID) -> bool:
    return db.query(CategoryGroups.id).filter(CategoryGroups.id == group_id).first() is not None


def lock_family(db: Session, family_id: UUID) -> None:
    """Serialise changes to a family's categories, so two requests cannot both take the same name."""
    db.query(Families).filter(Families.id == family_id).with_for_update().one()


def name_is_taken(db: Session, family_id: UUID, name: str, except_id: UUID | None = None) -> bool:
    """True if a default category or one of the family's has this name, ignoring case, surrounding spaces and emoji.

    Compared here and not in SQL, so the case rules are Python's (they cover accents) whatever the database locale.
    """
    rows = db.query(Categories.id, Categories.name).filter(_visible(family_id)).all()
    return any(row.id != except_id and same_name(row.name, name) for row in rows)


def create_category(db: Session, family_id: UUID, name: str, group_id: UUID | None) -> Categories:
    # Without a group the column's default puts it in "Outros"
    extra = {} if group_id is None else {"group_id": group_id}
    category = Categories(name=name, family_id=family_id, **extra)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: Categories, name: str | None, group_id: UUID | None) -> Categories:
    if name is not None:
        category.name = name
    if group_id is not None:
        category.group_id = group_id
        if db.query(CategoryGroups.name).filter(CategoryGroups.id == group_id).scalar() in UNBUDGETED_GROUPS:
            delete_budgets_of_category(db, category.id)  # income and transfers have no budget: do not keep hidden ones
    db.commit()
    db.refresh(category)
    return category


def count_transactions_using(db: Session, category_id: UUID) -> int:
    return db.query(TransactionDB.id).filter(TransactionDB.category_id == category_id).count()


def delete_category(db: Session, category: Categories) -> None:
    delete_budgets_of_category(db, category.id)  # a budget has no meaning without its category
    db.delete(category)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def group_name_of(db: Session, category: Categories) -> str:
    return db.query(CategoryGroups.name).filter(CategoryGroups.id == category.group_id).scalar()


def group_position_of(db: Session, category: Categories) -> int:
    return db.query(CategoryGroups.position).filter(CategoryGroups.id == category.group_id).scalar()

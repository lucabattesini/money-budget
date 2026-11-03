from datetime import date, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from schemas.tables import Budgets, Categories, CategoryGroups

# Money coming in and money moving between accounts are not spending: there is nothing to budget there
UNBUDGETED_GROUPS = ("Receitas", "Transferências")


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """The first moment of the month and the first moment of the next one (the end is not included)."""
    start = datetime(month.year, month.month, 1)
    end = datetime(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return start, end


def budgetable_categories(db: Session, family_id: int):
    """The categories the family can plan money for, each with its group, in the order the groups are shown."""
    return (
        db.query(Categories, CategoryGroups)
        .join(CategoryGroups, Categories.group_id == CategoryGroups.id)
        .filter(or_(Categories.family_id.is_(None), Categories.family_id == family_id))
        .filter(CategoryGroups.name.notin_(UNBUDGETED_GROUPS))
        .order_by(CategoryGroups.id, Categories.id)
        .all()
    )


def budgets_of_month(db: Session, family_id: int, month: date) -> dict[int, int]:
    """category id -> planned cents, for the month."""
    rows = db.query(Budgets.category_id, Budgets.amount).filter(Budgets.family_id == family_id, Budgets.month == month)
    return dict(rows.all())


def set_budget(db: Session, family_id: int, category_id: int, month: date, amount: int) -> None:
    """Plan `amount` cents for the category in the month; 0 removes the budget."""
    row = (
        db.query(Budgets)
        .filter(Budgets.family_id == family_id, Budgets.category_id == category_id, Budgets.month == month)
        .first()
    )
    if amount == 0:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Budgets(family_id=family_id, category_id=category_id, month=month, amount=amount))
    else:
        row.amount = amount
    db.commit()


def copy_budgets(db: Session, family_id: int, from_month: date, to_month: date) -> int:
    """Copy the budgets of one month to another, only for the categories that have none there yet.
    Returns how many were copied."""
    already = budgets_of_month(db, family_id, to_month)
    copied = 0
    for category_id, amount in budgets_of_month(db, family_id, from_month).items():
        if category_id not in already:
            db.add(Budgets(family_id=family_id, category_id=category_id, month=to_month, amount=amount))
            copied += 1
    db.commit()
    return copied


def delete_budgets_of_category(db: Session, category_id: int) -> None:
    """A category that goes takes its budgets with it (the caller commits)."""
    db.query(Budgets).filter(Budgets.category_id == category_id).delete(synchronize_session=False)

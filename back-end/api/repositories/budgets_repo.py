from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from schemas.tables import Budgets, Categories, CategoryGroups, TransactionDB, Users

# Money coming in and money moving between accounts are not spending: there is nothing to budget there
UNBUDGETED_GROUPS = ("Receitas", "Transferências")


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """The first moment of the month and the first moment of the next one (the end is not included)."""
    start = datetime(month.year, month.month, 1)
    end = datetime(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return start, end


def budgetable_categories(db: Session, family_id: UUID):
    """The categories the family can plan money for, each with its group, in the order the groups are shown."""
    return (
        db.query(Categories, CategoryGroups)
        .join(CategoryGroups, Categories.group_id == CategoryGroups.id)
        .filter(or_(Categories.family_id.is_(None), Categories.family_id == family_id))
        .filter(CategoryGroups.name.notin_(UNBUDGETED_GROUPS))
        .order_by(CategoryGroups.position, CategoryGroups.id, Categories.name, Categories.id)
        .all()
    )


def effective_budgets(db: Session, family_id: UUID, month: date) -> dict[UUID, tuple[int, date]]:
    """What the family has planned for the month, by category: category id -> (cents, the month the amount was set).

    A plan stays in force until it is changed: a month with no row of its own uses the most recent earlier one.
    A row with no amount is the family saying "no plan from this month on", so that category has none until a later
    row. A row of 0 is a plan: spend nothing.
    """
    rows = (
        db.query(Budgets.category_id, Budgets.month, Budgets.amount)
        .filter(Budgets.family_id == family_id, Budgets.month <= month)
        .order_by(Budgets.month)
        .all()
    )
    latest: dict[UUID, tuple[int, date]] = {}
    for category_id, set_in, amount in rows:  # oldest first, so the last one for a category wins
        latest[category_id] = (amount, set_in)
    return {category_id: found for category_id, found in latest.items() if found[0] is not None}


def _amount_before(db: Session, family_id: UUID, category_id: UUID, month: date) -> int | None:
    """What would be planned for the category in the month if the month had no row of its own (None: no plan)."""
    row = (
        db.query(Budgets.amount)
        .filter(Budgets.family_id == family_id, Budgets.category_id == category_id, Budgets.month < month)
        .order_by(Budgets.month.desc())
        .first()
    )
    return row.amount if row else None


def set_budget(db: Session, family_id: UUID, category_id: UUID, month: date, amount: int | None) -> None:
    """Plan `amount` cents for the category from this month on (until a later month changes it); 0 is a plan to
    spend nothing and None removes the plan.

    A row is only kept when it says something the earlier months do not: asking for what already applies from an
    earlier month removes this month's own row, so the month goes back to following the earlier plan.
    """
    row = (
        db.query(Budgets)
        .filter(Budgets.family_id == family_id, Budgets.category_id == category_id, Budgets.month == month)
        .first()
    )
    if amount == _amount_before(db, family_id, category_id, month):
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Budgets(family_id=family_id, category_id=category_id, month=month, amount=amount))
    else:
        row.amount = amount
    db.commit()


def delete_budgets_of_category(db: Session, category_id: UUID) -> None:
    """A category that goes takes its budgets with it (the caller commits)."""
    db.query(Budgets).filter(Budgets.category_id == category_id).delete(synchronize_session=False)


def planned_by_month(db: Session, family_id: UUID, category_id: UUID, months: list[date]) -> dict[date, int | None]:
    """What was planned for one category in each of the months (cents; None: no plan), by the same rule as
    `effective_budgets`: a plan stays in force until a later month changes it, and a row with no amount ends it."""
    rows = (
        db.query(Budgets.month, Budgets.amount)
        .filter(Budgets.family_id == family_id, Budgets.category_id == category_id, Budgets.month <= max(months))
        .order_by(Budgets.month)
        .all()
    )
    result: dict[date, int | None] = {}
    current: int | None = None
    position = 0
    for month in sorted(months):
        while position < len(rows) and rows[position].month <= month:
            current = rows[position].amount
            position += 1
        result[month] = current
    return result


def spent_by_month(db: Session, family_id: UUID, category_id: UUID, start: datetime, end: datetime) -> dict[date, int]:
    """What was spent in one category, month by month (the first day of the month -> cents): spending only, and not
    what the person left out of the totals, like every sum. `end` is not included."""
    month = func.date_trunc("month", TransactionDB.transactioned_at)
    rows = (
        db.query(month.label("month"), func.sum(TransactionDB.value))
        .filter(
            TransactionDB.family_id == family_id,
            TransactionDB.category_id == category_id,
            TransactionDB.type == "debit",
            TransactionDB.excluded.is_(False),
            TransactionDB.transactioned_at >= start,
            TransactionDB.transactioned_at < end,
        )
        .group_by(month)
        .all()
    )
    return {row[0].date(): int(row[1]) for row in rows}


def category_spending(db: Session, family_id: UUID, category_id: UUID, start: datetime, end: datetime):
    """The spending (debits) of one category in a period, newest first, each with the name of the person it belongs
    to. The ones left out of the totals are listed too (they carry `excluded`). `end` is not included."""
    return (
        db.query(TransactionDB, Users.name)
        .join(Users, TransactionDB.user_id == Users.id)
        .filter(
            TransactionDB.family_id == family_id,
            TransactionDB.category_id == category_id,
            TransactionDB.type == "debit",
            TransactionDB.transactioned_at >= start,
            TransactionDB.transactioned_at < end,
        )
        .order_by(TransactionDB.transactioned_at.desc(), TransactionDB.id)
        .all()
    )

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.budgets_repo import (
    budgetable_categories,
    category_spending,
    effective_budgets,
    month_bounds,
    planned_by_month,
    set_budget,
    spent_by_month,
)
from api.repositories.categories_repo import lock_family
from api.repositories.transactions_repo import get_transactions_summed_by_category
from api.utils.budget_order import category_sort_key


def month_key(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def parse_month(text: str) -> date:
    """ "2026-11" -> the first day of that month. The format is already checked by the request schema."""
    year, month = text.split("-")
    return date(int(year), int(month), 1)


def get_month_budget(db: Session, family_id: UUID, month_text: str) -> dict:
    """The family's plan and spending for one month, by group and category. Amounts are in cents.

    A plan stays in force until it is changed, so `budgeted` is the amount of the latest month up to this one that
    set one, and `since` says which month that was (the month itself when it was set here).

    `totals.spent` only counts the categories that have a budget, so it can be compared with `totals.budgeted`;
    what was spent in categories without one is `totals.unbudgeted_spent`.
    """
    month = parse_month(month_text)
    start, end = month_bounds(month)
    planned = effective_budgets(db, family_id, month)
    spent = {row.category_id: int(row.total) for row in get_transactions_summed_by_category(db, start, end, family_id)}

    groups: dict[UUID, dict] = {}
    for category, group in budgetable_categories(db, family_id):
        entry = groups.setdefault(group.id, {"id": group.id, "name": group.name, "categories": []})
        entry["categories"].append(
            {
                "id": category.id,
                "name": category.name,
                "budgeted": planned[category.id][0] if category.id in planned else None,
                "since": month_key(planned[category.id][1]) if category.id in planned else None,
                "spent": spent.get(category.id, 0),
            }
        )

    result = []
    totals = {"budgeted": 0, "spent": 0, "unbudgeted_spent": 0}
    for entry in groups.values():
        entry["categories"].sort(key=lambda c: category_sort_key(entry["name"], c["name"]))
        entry["budgeted"] = sum(c["budgeted"] or 0 for c in entry["categories"])
        entry["spent"] = sum(c["spent"] for c in entry["categories"] if c["budgeted"] is not None)
        totals["budgeted"] += entry["budgeted"]
        totals["spent"] += entry["spent"]
        totals["unbudgeted_spent"] += sum(c["spent"] for c in entry["categories"] if c["budgeted"] is None)
        result.append(entry)
    totals["remaining"] = totals["budgeted"] - totals["spent"]  # negative when over
    return {"month": month_text, "totals": totals, "groups": result}


def set_category_budget(db: Session, family_id: UUID, category_id: UUID, month_text: str, amount: int | None) -> dict:
    # Under the same lock the categories use: two requests cannot both create the row, and a category being deleted
    # at this very moment is seen as gone
    lock_family(db, family_id)
    allowed = {category.id for category, _ in budgetable_categories(db, family_id)}
    if category_id not in allowed:
        # Another family's category, an income or transfer one and an id that does not exist answer the same
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")
    set_budget(db, family_id, category_id, parse_month(month_text), amount)
    return get_month_budget(db, family_id, month_text)


def _months_back(last: date, count: int) -> list[date]:
    """The `count` months ending at `last` (included), oldest first. Never before the year 2000."""
    months = []
    year, month = last.year, last.month
    for _ in range(count):
        if year < 2000:
            break
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def get_category_history(
    db: Session, family_id: UUID, category_id: UUID, month_text: str, months: int, show_text: str | None = None
) -> dict:
    """One category over time: for each of the last `months` months (ending at `month_text`) what was planned and what
    was spent, and the spending of one month (`show_text`, `month_text` unless told otherwise), transaction by
    transaction. Amounts are in cents.

    `history[].spent` counts like the budget page (debits not left out of the totals), so it matches what the page
    shows for that month; `transactions` also lists the ones left out, marked `excluded`.
    """
    found = next(
        ((category, group) for category, group in budgetable_categories(db, family_id) if category.id == category_id),
        None,
    )
    if found is None:
        # Another family's category, an income or transfer one and an id that does not exist answer the same
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")
    category, group = found

    month = parse_month(month_text)
    span = _months_back(month, months)
    spent = spent_by_month(db, family_id, category_id, month_bounds(span[0])[0], month_bounds(month)[1])
    planned = planned_by_month(db, family_id, category_id, span)

    shown = parse_month(show_text or month_text)
    start, end = month_bounds(shown)
    transactions = [
        {
            "id": transaction.id,
            "label": transaction.label,
            "value": transaction.value,
            "transactioned_at": transaction.transactioned_at,
            "excluded": transaction.excluded,
            "user_name": user_name,
        }
        for transaction, user_name in category_spending(db, family_id, category_id, start, end)
    ]
    return {
        "category": {"id": category.id, "name": category.name, "group_name": group.name},
        "month": month_text,
        "transactions_month": month_key(shown),
        "history": [{"month": month_key(day), "budgeted": planned[day], "spent": spent.get(day, 0)} for day in span],
        "transactions": transactions,
    }

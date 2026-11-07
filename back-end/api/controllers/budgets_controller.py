from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.budgets_repo import budgetable_categories, effective_budgets, month_bounds, set_budget
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
        entry["categories"].sort(key=lambda c: category_sort_key(c["name"]))
        entry["budgeted"] = sum(c["budgeted"] or 0 for c in entry["categories"])
        entry["spent"] = sum(c["spent"] for c in entry["categories"] if c["budgeted"])
        totals["budgeted"] += entry["budgeted"]
        totals["spent"] += entry["spent"]
        totals["unbudgeted_spent"] += sum(c["spent"] for c in entry["categories"] if not c["budgeted"])
        result.append(entry)
    totals["remaining"] = totals["budgeted"] - totals["spent"]  # negative when over
    return {"month": month_text, "totals": totals, "groups": result}


def set_category_budget(db: Session, family_id: UUID, category_id: UUID, month_text: str, amount: int) -> dict:
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

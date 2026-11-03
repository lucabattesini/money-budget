from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.budgets_repo import (
    budgetable_categories,
    budgets_of_month,
    copy_budgets,
    month_bounds,
    set_budget,
)
from api.repositories.transactions_repo import get_transactions_summed_by_category
from api.utils.category_names import name_key


def parse_month(text: str) -> date:
    """ "2026-11" -> the first day of that month. The format is already checked by the request schema."""
    year, month = text.split("-")
    return date(int(year), int(month), 1)


def get_month_budget(db: Session, family_id: int, month_text: str) -> dict:
    """The family's plan and spending for one month, by group and category. Amounts are in cents.

    `totals.spent` only counts the categories that have a budget, so it can be compared with `totals.budgeted`;
    what was spent in categories without one is `totals.unbudgeted_spent`.
    """
    month = parse_month(month_text)
    start, end = month_bounds(month)
    planned = budgets_of_month(db, family_id, month)
    spent = {row.category_id: int(row.total) for row in get_transactions_summed_by_category(db, start, end, family_id)}

    groups: dict[int, dict] = {}
    for category, group in budgetable_categories(db, family_id):
        entry = groups.setdefault(group.id, {"id": group.id, "name": group.name, "categories": []})
        entry["categories"].append(
            {
                "id": category.id,
                "name": category.name,
                "budgeted": planned.get(category.id),
                "spent": spent.get(category.id, 0),
            }
        )

    result = []
    totals = {"budgeted": 0, "spent": 0, "unbudgeted_spent": 0}
    for entry in groups.values():
        entry["categories"].sort(key=lambda c: name_key(c["name"]))  # A-Z by the words, whatever the emoji
        entry["budgeted"] = sum(c["budgeted"] or 0 for c in entry["categories"])
        entry["spent"] = sum(c["spent"] for c in entry["categories"] if c["budgeted"])
        totals["budgeted"] += entry["budgeted"]
        totals["spent"] += entry["spent"]
        totals["unbudgeted_spent"] += sum(c["spent"] for c in entry["categories"] if not c["budgeted"])
        result.append(entry)
    totals["remaining"] = totals["budgeted"] - totals["spent"]  # negative when over
    return {"month": month_text, "totals": totals, "groups": result}


def set_category_budget(db: Session, family_id: int, category_id: int, month_text: str, amount: int) -> dict:
    allowed = {category.id for category, _ in budgetable_categories(db, family_id)}
    if category_id not in allowed:
        # Another family's category, an income or transfer one and an id that does not exist answer the same
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")
    set_budget(db, family_id, category_id, parse_month(month_text), amount)
    return get_month_budget(db, family_id, month_text)


def copy_month_budgets(db: Session, family_id: int, from_text: str, to_text: str) -> dict:
    if from_text == to_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Escolha dois meses diferentes para copiar."
        )
    copied = copy_budgets(db, family_id, parse_month(from_text), parse_month(to_text))
    return {"copied": copied, **get_month_budget(db, family_id, to_text)}

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id
from api.controllers.budgets_controller import get_category_history, get_month_budget, set_category_budget
from db.connection import get_db
from schemas.tables_schemas import MONTH_PATTERN, BudgetSet

router = APIRouter(prefix="/budgets", tags=["budgets"], responses={404: {"description": "Not found"}})


def _ok(data):
    return JSONResponse(content={"data": jsonable_encoder(data)}, status_code=status.HTTP_200_OK)


# Both spellings, like /categories: the web app asks for "/budgets"
@router.get("")
@router.get("/")
async def get_budget_router(
    month: str = Query(pattern=MONTH_PATTERN, description="YYYY-MM"),
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """The plan and the spending of the family in one month, by group and category (cents)."""
    return _ok(get_month_budget(db, family_id, month))


@router.put("")
async def set_budget_router(
    params: BudgetSet, family_id: UUID = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    """Plan an amount for a category from a month on, until a later month changes it (0: nothing from then on).
    Answers with the month as `GET` shows it."""
    return _ok(set_category_budget(db, family_id, params.category_id, params.month, params.amount))


@router.get("/categories/{category_id}")
async def get_category_history_router(
    category_id: UUID,
    month: str = Query(pattern=MONTH_PATTERN, description="YYYY-MM: the last month of the history"),
    months: int = Query(6, ge=1, le=24, description="How many months of history, ending at `month`"),
    show: str | None = Query(
        None, pattern=MONTH_PATTERN, description="YYYY-MM: the month whose transactions are listed (default `month`)"
    ),
    family_id: UUID = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """One category over the last months (what was planned and spent in each) and the spending of `month`, one
    transaction at a time (cents)."""
    return _ok(get_category_history(db, family_id, category_id, month, months, show))

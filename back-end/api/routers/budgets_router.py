from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_family_id
from api.controllers.budgets_controller import copy_month_budgets, get_month_budget, set_category_budget
from db.connection import get_db
from schemas.tables_schemas import MONTH_PATTERN, BudgetCopy, BudgetSet

router = APIRouter(prefix="/budgets", tags=["budgets"], responses={404: {"description": "Not found"}})


def _ok(data):
    return JSONResponse(content={"data": jsonable_encoder(data)}, status_code=status.HTTP_200_OK)


# Both spellings, like /categories: the web app asks for "/budgets"
@router.get("")
@router.get("/")
async def get_budget_router(
    month: str = Query(pattern=MONTH_PATTERN, description="YYYY-MM"),
    family_id: int = Depends(get_current_family_id),
    db: Session = Depends(get_db),
):
    """The plan and the spending of the family in one month, by group and category (cents)."""
    return _ok(get_month_budget(db, family_id, month))


@router.put("")
async def set_budget_router(
    params: BudgetSet, family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    """Plan an amount for a category in a month (0 removes it). Answers with the month as `GET` shows it."""
    return _ok(set_category_budget(db, family_id, params.category_id, params.month, params.amount))


@router.post("/copy")
async def copy_budget_router(
    params: BudgetCopy, family_id: int = Depends(get_current_family_id), db: Session = Depends(get_db)
):
    """Copy a month's budgets to another month, only for the categories that have none there yet."""
    return _ok(copy_month_budgets(db, family_id, params.from_month, params.to_month))

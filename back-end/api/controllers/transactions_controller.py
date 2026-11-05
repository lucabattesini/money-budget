from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.families_repo import get_family
from api.repositories.transactions_repo import (
    category_exists,
)
from api.repositories.transactions_repo import (
    create_transaction as create_transaction_repo,
)
from api.repositories.transactions_repo import (
    delete_transaction as delete_transaction_repo,
)
from api.repositories.transactions_repo import (
    get_transactions as get_transactions_repo,
)
from api.repositories.transactions_repo import (
    get_transactions_summed_by_category as get_transactions_summed_by_category_repo,
)
from api.repositories.transactions_repo import (
    update_transaction as update_transaction_repo,
)
from api.utils.clock import family_now
from schemas.tables_schemas import GetTransactionsParams, Transaction, TransactionUpdate


def _parse_date(transaction: GetTransactionsParams):
    """Return the (start, end) of the period asked for, end excluded; (None, None) means no filter.

    "day" is that exact day, "month" that month of that year, "year" that year.
    """
    datetype = transaction.organized_by
    if datetype is None:
        return None, None
    d = transaction.date
    if datetype == "year":
        start, end = datetime(d.year, 1, 1), (d.year + 1, 1, 1)
    elif datetype == "month":
        start = datetime(d.year, d.month, 1)
        end = (d.year + 1, 1, 1) if d.month == 12 else (d.year, d.month + 1, 1)
    else:
        start = datetime(d.year, d.month, d.day)
        end = None if start.date() == date.max else start + timedelta(days=1)
    if isinstance(end, tuple):
        # Past the last year the calendar has, the period simply has no upper limit
        end = datetime(*end) if end[0] <= datetime.max.year else None
    return start, end


def create_transaction(db: Session, transaction: Transaction, family_id: int, user_id: int):
    if transaction.category_id is not None and not category_exists(db, transaction.category_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    # No date given: "now" on the family's clock, not the server's (TKT-65)
    transaction.transactioned_at = transaction.transactioned_at or family_now(get_family(db, family_id).timezone)
    return create_transaction_repo(db, transaction, family_id, user_id)


def get_transactions(db: Session, transaction: GetTransactionsParams, family_id: int):
    start, end = _parse_date(transaction)
    return get_transactions_repo(db, start, end, family_id)


def get_transactions_summed_by_category(db: Session, transaction: GetTransactionsParams, family_id: int):
    start, end = _parse_date(transaction)
    rows = get_transactions_summed_by_category_repo(db, start, end, family_id)
    return [{"category_id": category_id, "total": total} for category_id, total in rows]


def delete_transaction(db: Session, id, family_id: int):
    # Same answer for "missing" and "another family's", so other families' ids are not revealed
    if not delete_transaction_repo(db, id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return {"message": "Transaction deleted"}


def update_transaction(db: Session, id: int, changes: TransactionUpdate, family_id: int):
    if not category_exists(db, changes.category_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    # Same answer for "missing" and "another family's", so other families' ids are not revealed
    transaction = update_transaction_repo(db, id, family_id, changes)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return {
        "id": transaction.id,
        "label": transaction.label,
        "value": transaction.value,
        "type": transaction.type,
        "transactioned_at": transaction.transactioned_at,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
        "category_id": transaction.category_id,
    }

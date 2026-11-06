from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.controllers.merchants_controller import merchant_for_transaction
from api.repositories.families_repo import get_family, is_member
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


def _check_person(db: Session, person_id: UUID | None, family_id: UUID):
    """The person a transaction belongs to must be in the family. Same answer for "missing" and "another family's"."""
    if person_id is not None and not is_member(db, person_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")


def create_transaction(db: Session, transaction: Transaction, family_id: UUID, user_id: UUID):
    if transaction.category_id is not None and not category_exists(db, transaction.category_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    _check_person(db, transaction.user_id, family_id)
    # No date given: "now" on the family's clock, not the server's (TKT-65)
    transaction.transactioned_at = transaction.transactioned_at or family_now(get_family(db, family_id).timezone)
    merchant_id = merchant_for_transaction(db, family_id, transaction.merchant)
    return create_transaction_repo(db, transaction, family_id, user_id, merchant_id)


def get_transactions(db: Session, transaction: GetTransactionsParams, family_id: UUID):
    start, end = _parse_date(transaction)
    return get_transactions_repo(db, start, end, family_id)


def get_transactions_summed_by_category(db: Session, transaction: GetTransactionsParams, family_id: UUID):
    start, end = _parse_date(transaction)
    rows = get_transactions_summed_by_category_repo(db, start, end, family_id)
    return [{"category_id": category_id, "total": total} for category_id, total in rows]


def delete_transaction(db: Session, id, family_id: UUID):
    # Same answer for "missing" and "another family's", so other families' ids are not revealed
    if not delete_transaction_repo(db, id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return {"message": "Transaction deleted"}


def update_transaction(db: Session, id: UUID, changes: TransactionUpdate, family_id: UUID):
    if not category_exists(db, changes.category_id, family_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    _check_person(db, changes.user_id, family_id)
    # Same answer for "missing" and "another family's", so other families' ids are not revealed
    merchant_id = merchant_for_transaction(db, family_id, changes.merchant)
    transaction = update_transaction_repo(db, id, family_id, changes, merchant_id)
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
        "user_id": transaction.user_id,
        "merchant_id": transaction.merchant_id,
        "excluded": transaction.excluded,
    }

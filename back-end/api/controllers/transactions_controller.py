from datetime import datetime
from sqlalchemy.orm import Session
from api.repositories.transactions_repo import (
    create_transaction as create_transaction_repo,
    get_transactions_summed_by_category as get_transactions_summed_by_category_repo,
    delete_transaction as delete_transaction_repo,
    get_transactions as get_transactions_repo,
)
from schemas.tables_schemas import Transaction, GetTransactionsParams


def _parse_date(transaction: GetTransactionsParams):
    """Return (datetype, formatted_date) from filter params."""
    datetype = transaction.organized_by
    if datetype == "year":
        return datetype, transaction.date.strftime("%Y")
    elif datetype == "month":
        return datetype, transaction.date.strftime("%m")
    elif datetype == "day":
        return datetype, transaction.date.strftime("%d")
    return None, None


def create_transaction(db: Session, transaction: Transaction, user_id: int):
    transaction.date = datetime.now()
    return create_transaction_repo(db, transaction, user_id)


def get_transactions(db: Session, transaction: GetTransactionsParams, user_id: int):
    datetype, formatted_date = _parse_date(transaction)
    return get_transactions_repo(db, datetype, formatted_date, user_id)


def get_transactions_summed_by_category(db: Session, transaction: GetTransactionsParams, user_id: int):
    datetype, formatted_date = _parse_date(transaction)
    rows = get_transactions_summed_by_category_repo(db, datetype, formatted_date, user_id)
    return [{"category_id": category_id, "total": total} for category_id, total in rows]


def delete_transaction(db: Session, id, user_id: int):
    return delete_transaction_repo(db, id, user_id)
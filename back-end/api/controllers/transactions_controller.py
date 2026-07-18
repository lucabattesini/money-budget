from datetime import datetime
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


def create_transaction(transaction: Transaction, user_id: int):
    transaction.date = datetime.now()
    return create_transaction_repo(transaction, user_id)


def get_transactions(transaction: GetTransactionsParams, user_id: int):
    datetype, formatted_date = _parse_date(transaction)
    return get_transactions_repo(datetype, formatted_date, user_id)


def get_transactions_summed_by_category(transaction: GetTransactionsParams, user_id: int):
    datetype, formatted_date = _parse_date(transaction)
    rows = get_transactions_summed_by_category_repo(datetype, formatted_date, user_id)
    return [{"category": category, "total": total} for category, total in rows]


def delete_transaction(id, user_id: int):
    return delete_transaction_repo(id, user_id)
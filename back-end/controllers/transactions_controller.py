from datetime import datetime
from repositories.transactions_repo import create_transaction as create_transaction_repo, get_transactions_summed_by_category as get_transactions_summed_by_category_repo, get_all_transactions as get_all_transactions_repo
from schemas.tables_schemas import Transaction

def create_transaction(transaction: Transaction):
    transaction.date = datetime.now()
    object = create_transaction_repo(transaction)

    return object

def get_all_transactions():
    return get_all_transactions_repo()

def get_added_transactions_by_category():
    today = datetime.now()
    month = int(today.month)
    year = int(today.year)
    added_categories = get_transactions_summed_by_category_repo(month, year)
    total = [{"category": category, "total": total} for category, total in added_categories]
    return total
from datetime import datetime
from repositories.transactions_repo import create_transaction as create_transaction_repo, get_transactions_summed_by_category as get_transactions_summed_by_category_repo, get_all_transactions as get_all_transactions_repo, delete_transaction as delete_transaction_repo
from schemas.tables_schemas import Transaction

def create_transaction(transaction: Transaction):
    transaction.date = datetime.now()
    object = create_transaction_repo(transaction)
    return object

def get_all_transactions():
    all_transactions = get_all_transactions_repo()
    increasing_ordered_list = sorted(all_transactions, key=lambda e: e.date)
    decreasing_ordered_list = []
    for r in increasing_ordered_list:
        decreasing_ordered_list.insert(0, r)
    return decreasing_ordered_list

def get_transactions_summed_by_category():
    today = datetime.now()
    month = int(today.month)
    year = int(today.year)
    summed_transactions_by_categories = get_transactions_summed_by_category_repo(month, year)
    total = [{"category": category, "total": total} for category, total in summed_transactions_by_categories]
    return total

def delete_transaction(id):
    return delete_transaction_repo(id)
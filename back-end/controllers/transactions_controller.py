from datetime import datetime
from repositories.transactions_repo import create_transaction as create_transaction_repo, get_transactions_summed_by_category as get_transactions_summed_by_category_repo, get_all_transactions as get_all_transactions_repo
from schemas.tables_schemas import Transaction

# Return the created object
def create_transaction(transaction: Transaction):
    today = datetime.now()
    transaction.date = today
    object = create_transaction_repo(transaction)

    return object

def get_all_transactions():
    return get_all_transactions_repo()

def get_added_transactions_by_category(month, year):
    return get_transactions_summed_by_category_repo(month, year)
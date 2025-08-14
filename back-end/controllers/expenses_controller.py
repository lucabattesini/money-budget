from datetime import datetime
from repositories.expenses_repo import report_transaction_repo, get_all_transactions_repo, get_added_transactions_by_category_repo

# Return the created object
def report_transaction_ctrl(label, value, category):
    today = datetime.now()
    object = report_transaction_repo(label, value, today, category)
    
    return object

def get_all_transactions_ctrl():
    return get_all_transactions_repo()

def get_added_transactions_by_category_ctrl():
    return get_added_transactions_by_category_repo()
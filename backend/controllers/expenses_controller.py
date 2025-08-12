from datetime import datetime, timedelta
from repositories.expenses_repo import report_transaction_repo, get_all_transactions_repo
from fastapi import status

# Return the created object
def report_transaction_ctrl(label, value, category):
    today = datetime.now()
    report_transaction_repo(label, value, today, category)
    
    return status.HTTP_202_ACCEPTED

def get_all_transactions_ctrl():
    transactions = get_all_transactions_repo()
    
    return transactions

def get_transactions_by_time_ctrl(time):
    time = int(time)
    transactions = get_all_transactions_repo()
    today = datetime.now()
    filtered_transactions = [
        r for r in transactions
        if (today - r.date).days <= time
    ]

    return filtered_transactions
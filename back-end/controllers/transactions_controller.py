from datetime import datetime
from repositories.transactions_repo import create_transaction as create_transaction_repo, get_transactions_summed_by_category as get_transactions_summed_by_category_repo, delete_transaction as delete_transaction_repo, get_transactions as get_transactions_repo
from schemas.tables_schemas import Transaction, GetTransactionsParams
 
def create_transaction(transaction: Transaction):
    transaction.date = datetime.now()
    object = create_transaction_repo(transaction)
    return object

def get_transactions(transaction: GetTransactionsParams):
    datetype = transaction.organized_by
    if datetype == "year":
        formated_date = transaction.date.strftime("%Y")
    elif datetype == "month":
        formated_date = transaction.date.strftime("%m")
    elif datetype == "day":
        formated_date = transaction.date.strftime("%d")
    else:
        formated_date = None
    
    return get_transactions_repo(datetype, formated_date)

def get_transactions_summed_by_category(transaction: GetTransactionsParams):
    datetype = transaction.organized_by
    if datetype == "year":
        formated_date = transaction.date.strftime("%Y")
    elif datetype == "month":
        formated_date = transaction.date.strftime("%m")
    elif datetype == "day":
        formated_date = transaction.date.strftime("%d")
    else:
        formated_date = None

    summed_transactions_by_categories = get_transactions_summed_by_category_repo(datetype, formated_date)
    total = [{"category": category, "total": total} for category, total in summed_transactions_by_categories]
    return total

def delete_transaction(id):
    return delete_transaction_repo(id)
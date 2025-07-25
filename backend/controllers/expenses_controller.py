from repositories.expenses_repo import insert_transaction
from datetime import date

today = date.today()

def format_transaction_to_insert(label, value, category):
    insert_transaction(label, value, date, category)
    return
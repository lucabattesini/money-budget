from datetime import date
from repositories.expenses_repo import report_transaction_repo

def report_transaction_ctrl(label, value, category):
    today = date.today()
    report_transaction_repo(label, value, today, category)
    
    return {"message": "Data sent succesfully"}
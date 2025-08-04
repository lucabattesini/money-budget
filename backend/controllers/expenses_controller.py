from datetime import datetime
from repositories.expenses_repo import report_transaction_repo, get_all_transactions_repo
from fastapi.encoders import jsonable_encoder

def report_transaction_ctrl(label, value, category):
    today = datetime.now()
    report_transaction_repo(label, value, today, category)
    
    return {"message": "Data sent succesfully"}

def get_all_transactions_ctrl():
    transactions = get_all_transactions_repo()
    json_result = jsonable_encoder(transactions)
    
    return json_result
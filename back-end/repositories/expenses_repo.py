from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Transactions

def report_transaction_repo(label, value, date, category):
    db: Session = LocalSession()

    try:
        db.add(Transactions(label=label, value=value, date=date, category=category))
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()
    
    return {"label": label, "value": value, "date": date, "category": category}


def get_all_transactions_repo():
    db : Session = LocalSession()

    transactions = db.query(Transactions).all()

    return transactions
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
    
    return {"message": "Transaction created successfully"}
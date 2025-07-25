from sqlalchemy.orm import Session
from db.connection import LocalSession
from schemas.tables import Transactions

def insert_transaction(label, value, date, category):
    db: Session = LocalSession()

    try:
        db.add(Transactions(
            label=label,
            value=value,
            date=date,
            category=category
        ))
        db.commit()
        print("Transaction inserted into DB successfully")
    except Exception as e:
        db.rollback()
        print("An error occurred while inserting the transaction")
    finally:
        db.close()
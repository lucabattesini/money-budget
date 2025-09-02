from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import TransactionDB
from schemas.tables_schemas import Transaction

db: Session = LocalSession()

def create_transaction(t: Transaction):
    try:
        transaction = TransactionDB(**t.dict())
        db.add(transaction)
        db.commit()
        return t
    
    except Exception as e:
        db.rollback()
        raise

def get_all_transactions():
    return db.query(TransactionDB).all()

def get_transactions_summed_by_category(month, year):
    added_categoiries = (
        db.query(
            TransactionDB.category,
            func.sum(TransactionDB.value).label("total"))
            .filter(extract("month", TransactionDB.date) == month)
            .filter(extract("year", TransactionDB.date) == year)
            .group_by(TransactionDB.category)
            .all()
    )

    return added_categoiries
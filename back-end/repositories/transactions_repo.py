from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import TransactionsDB
from schemas.tables_schemas import Transaction

db: Session = LocalSession()

def create_transaction(t: Transaction):
    try:
        transaction = TransactionsDB(**t.dict())
        db.add(transaction)
        db.commit()
        return t
    
    except Exception as e:
        db.rollback()
        raise

def get_all_transactions():
    return db.query(TransactionsDB).all()

def get_transactions_summed_by_category(month, year):
    added_categoiries = (
        db.query(
            TransactionsDB.category,
            func.sum(TransactionsDB.value).label("total"))
            .filter(extract("month", TransactionsDB.date) == month)
            .filter(extract("year", TransactionsDB.date) == year)
            .group_by(TransactionsDB.category)
            .all()
    )

    return added_categoiries
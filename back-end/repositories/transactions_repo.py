from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import Transactions

db: Session = LocalSession()

def create_transaction(t):
    try:
        db.add(Transactions(
            label=t.label,
            value=t.value,
            date=t.date,
            category=t.category
        ))
        db.commit()
        return t
    
    except Exception as e:
        db.rollback()
        raise

def get_all_transactions():
    return db.query(Transactions).all()

def get_transactions_summed_by_category(month, year):
    added_categoiries = (
        db.query(
            Transactions.category,
            func.sum(Transactions.value).label("total"))
            .filter(extract("month", Transactions.date) == month)
            .filter(extract("year", Transactions.date) == year)
            .group_by(Transactions.category)
            .all()
    )

    return added_categoiries
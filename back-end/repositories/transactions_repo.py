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

def get_transactions(datetype, date):
    query = db.query(TransactionDB)
    if datetype ==  None:
        filtered_transactions = query.order_by(TransactionDB.date.desc()).all()
    else:
        filtered_transactions = query.filter(
            extract(datetype, TransactionDB.date) == date
        ).order_by(TransactionDB.date.desc()).all()

    return filtered_transactions

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

def delete_transaction(id):
    transaction = db.query(TransactionDB).filter_by(id=id).first()
    if transaction:
        db.delete(transaction)
        db.commit()
        return transaction
    else:
        return {"message": "Transaction not found"}

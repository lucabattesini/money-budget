from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import TransactionDB
from schemas.tables_schemas import Transaction

db: Session = LocalSession()

def create_transaction(t: Transaction, user_id: int):
    try:
        transaction = TransactionDB(**t.dict(), user_id=user_id)
        db.add(transaction)
        db.commit()
        return t
    except Exception as e:
        db.rollback()
        raise

def get_transactions(datetype, date, user_id: int):
    query = db.query(TransactionDB).filter(TransactionDB.user_id == user_id)
    if datetype is None:
        return query.order_by(TransactionDB.date.desc()).all()
    return query.filter(
        extract(datetype, TransactionDB.date) == date
    ).order_by(TransactionDB.date.desc()).all()

def get_transactions_summed_by_category(datetype, date, user_id: int):
    query = db.query(
        TransactionDB.category,
        func.sum(TransactionDB.value).label("total")
    ).filter(TransactionDB.user_id == user_id).group_by(TransactionDB.category)

    if datetype is not None:
        query = query.filter(extract(datetype, TransactionDB.date) == date)

    return query.all()

def delete_transaction(id, user_id: int):
    transaction = db.query(TransactionDB).filter_by(id=id, user_id=user_id).first()
    if transaction:
        db.delete(transaction)
        db.commit()
        return transaction
    return {"message": "Transaction not found"}

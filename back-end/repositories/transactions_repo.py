from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from db.connection import LocalSession
from schemas.tables import Transactions

# Change names usaing as in all the files

# Adjust the function to just do "Repositories" stuff
db: Session = LocalSession()
#Melhorar nomes da funções
def create_transaction(t):
    try:
        db.add(Transactions(
            label=t.label,
            value=t.value,
            date=t.date,
            category=t.category
        ))
        db.commit()
        db.close()
        return t
    except Exception as e:
        db.rollback()
    # Returning everything here and "trate" it in controller

def get_all_transactions():
    try:
        return db.query(Transactions).all()
    except Exception as e:
        db.rollback()
# Repositorio deve ser genérico
# Função 2 e 3 devem ser a mesma - config via params
# Improve func name
# Deixar as funções parecidas- entender o codigo
def get_transactions_summed_by_category(month, year):
    try:
        added_categoiries = (
            db.query(
                Transactions.category,
                func.sum(Transactions.value).label("total"))
                .filter(extract("month", Transactions.date) == month)
                .filter(extract("year", Transactions.date) == year)
                .group_by(Transactions.category)
                .all()
        )
    except Exception as e:
        db.rollback()
        raise

    total = [{"category": category, "total": total} for category, total in added_categoiries]
    return total
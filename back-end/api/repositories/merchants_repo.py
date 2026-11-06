from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.utils.category_names import name_key, same_name
from schemas.tables import Merchants, TransactionDB


def list_merchants(db: Session, family_id: UUID) -> list[tuple[Merchants, int]]:
    """The family's merchants with how many transactions use each, in alphabetical order of their words."""
    rows = (
        db.query(Merchants, func.count(TransactionDB.id))
        .outerjoin(TransactionDB, TransactionDB.merchant_id == Merchants.id)
        .filter(Merchants.family_id == family_id)
        .group_by(Merchants.id)
        .all()
    )
    return sorted(rows, key=lambda row: (name_key(row[0].name), row[0].id))


def get_family_merchant(db: Session, family_id: UUID, merchant_id: UUID) -> Merchants | None:
    return db.query(Merchants).filter(Merchants.id == merchant_id, Merchants.family_id == family_id).first()


def find_by_name(db: Session, family_id: UUID, name: str, except_id: UUID | None = None) -> Merchants | None:
    """The family's merchant with these words, ignoring case, accents and emoji. Compared here and not in SQL so the
    rules are the same as for categories whatever the database locale."""
    for merchant in db.query(Merchants).filter(Merchants.family_id == family_id).order_by(Merchants.id):
        if merchant.id != except_id and same_name(merchant.name, name):
            return merchant
    return None


def create_merchant(db: Session, family_id: UUID, name: str) -> Merchants:
    merchant = Merchants(family_id=family_id, name=name)
    db.add(merchant)
    db.commit()
    return merchant


def rename_merchant(db: Session, merchant: Merchants, name: str) -> Merchants:
    merchant.name = name
    db.commit()
    return merchant


def count_transactions_using(db: Session, merchant_id: UUID) -> int:
    return db.query(func.count(TransactionDB.id)).filter(TransactionDB.merchant_id == merchant_id).scalar()


def delete_merchant(db: Session, merchant: Merchants) -> None:
    db.delete(merchant)
    db.commit()

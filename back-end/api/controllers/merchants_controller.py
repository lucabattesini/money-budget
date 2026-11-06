from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.repositories.categories_repo import lock_family
from api.repositories.families_repo import get_family
from api.repositories.merchants_repo import (
    count_transactions_using,
    create_merchant,
    delete_merchant,
    find_by_name,
    get_family_merchant,
    rename_merchant,
)
from api.repositories.merchants_repo import list_merchants as list_merchants_repo
from api.utils.category_names import name_key
from schemas.tables import Merchants

MAX_NAME_LENGTH = 100  # the size of the column


def _out(merchant: Merchants, used: int) -> dict:
    return {"id": merchant.id, "name": merchant.name, "transactions": used}


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name_key(name):  # nothing, or only an emoji or invisible characters: it needs words to be told apart
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O nome do estabelecimento não pode ficar vazio."
        )
    if len(name) > MAX_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"O nome do estabelecimento pode ter no máximo {MAX_NAME_LENGTH} caracteres.",
        )
    return name


def _duplicate() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um estabelecimento com esse nome.")


def _not_found() -> HTTPException:
    # Missing and another family's look the same
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estabelecimento não encontrado.")


def _in_use(used: int) -> HTTPException:
    if used == 1:
        detail = "Este estabelecimento é usado por 1 transação. Mude o estabelecimento dela ou apague-a antes."
    else:
        detail = f"Este estabelecimento é usado por {used} transações. Mude o estabelecimento delas ou apague-as antes."
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def list_merchants(db: Session, family_id: UUID) -> list[dict]:
    return [_out(merchant, used) for merchant, used in list_merchants_repo(db, family_id)]


def create_family_merchant(db: Session, family_id: UUID, name: str) -> dict:
    name = _clean_name(name)
    lock_family(db, family_id)
    if find_by_name(db, family_id, name):
        db.rollback()
        raise _duplicate()
    return _out(create_merchant(db, family_id, name), 0)


def rename_family_merchant(db: Session, family_id: UUID, merchant_id: UUID, name: str) -> dict:
    cleaned = _clean_name(name)
    lock_family(db, family_id)
    merchant = get_family_merchant(db, family_id, merchant_id)
    if merchant is None:
        db.rollback()
        raise _not_found()
    if find_by_name(db, family_id, cleaned, except_id=merchant.id):
        db.rollback()
        raise _duplicate()
    merchant = rename_merchant(db, merchant, cleaned)
    return _out(merchant, count_transactions_using(db, merchant.id))


def delete_family_merchant(db: Session, family_id: UUID, merchant_id: UUID) -> dict:
    lock_family(db, family_id)
    merchant = get_family_merchant(db, family_id, merchant_id)
    if merchant is None:
        db.rollback()
        raise _not_found()
    used = count_transactions_using(db, merchant.id)
    if used:
        db.rollback()
        raise _in_use(used)
    try:
        delete_merchant(db, merchant)
    except IntegrityError:
        # A transaction took the merchant between the count and the delete: same answer as "in use"
        db.rollback()
        raise _in_use(max(count_transactions_using(db, merchant_id), 1))
    return {"message": "Estabelecimento apagado"}


def merchant_for_transaction(db: Session, family_id: UUID, name: str | None) -> UUID | None:
    """The id of the family's merchant a transaction names, creating it the first time the name is used.

    None (the name was left out) and "" (empty: no merchant) both mean no merchant. Naming one while the family has
    merchants off is refused. Names that differ only by case, accents or an emoji are the same merchant.
    """
    if name is None or not name.strip():
        return None
    if not get_family(db, family_id).merchants_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Os estabelecimentos estão desligados para a sua família."
        )
    name = _clean_name(name)
    lock_family(db, family_id)
    merchant = find_by_name(db, family_id, name) or create_merchant(db, family_id, name)
    db.commit()  # release the family lock
    return merchant.id

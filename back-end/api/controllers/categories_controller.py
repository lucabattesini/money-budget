from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.repositories.categories_repo import (
    count_transactions_using,
    create_category,
    delete_category,
    get_family_category,
    group_exists,
    group_name_of,
    lock_family,
    name_is_taken,
    update_category,
)
from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
from api.repositories.categories_repo import get_all_groups as get_all_groups_repo
from api.utils.category_names import name_key
from schemas.tables import Categories

MAX_NAME_LENGTH = 100  # the size of the column


def _out(category: Categories, group_name: str) -> dict:
    return {
        "id": category.id,
        "family_id": category.family_id,
        "is_default": category.family_id is None,  # shown, but cannot be renamed or deleted
        "name": category.name,
        "group_id": category.group_id,
        "group_name": group_name,
    }


def get_all_categories(db: Session, family_id: UUID):
    return [_out(category, group_name) for category, group_name in get_all_categories_repo(db, family_id)]


def get_all_groups(db: Session):
    return [{"id": group.id, "name": group.name} for group in get_all_groups_repo(db)]


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name_key(name):  # nothing, or only an emoji or invisible characters: it needs words to be told apart
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O nome da categoria não pode ficar vazio."
        )
    if len(name) > MAX_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"O nome da categoria pode ter no máximo {MAX_NAME_LENGTH} caracteres.",
        )
    return name


def _check_group(db: Session, group_id: UUID | None) -> None:
    if group_id is not None and not group_exists(db, group_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Esse grupo não existe.")


def _duplicate() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma categoria com esse nome.")


def _not_found() -> HTTPException:
    # Missing, a default category (which cannot be changed) and another family's all look the same
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")


def create_family_category(db: Session, family_id: UUID, name: str, group_id: UUID | None) -> dict:
    name = _clean_name(name)
    _check_group(db, group_id)
    lock_family(db, family_id)
    if name_is_taken(db, family_id, name):
        db.rollback()
        raise _duplicate()
    category = create_category(db, family_id, name, group_id)
    return _out(category, group_name_of(db, category))


def update_family_category(
    db: Session, family_id: UUID, category_id: UUID, name: str | None, group_id: UUID | None
) -> dict:
    if name is None and group_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Informe o novo nome ou o novo grupo."
        )
    cleaned = None if name is None else _clean_name(name)
    _check_group(db, group_id)
    lock_family(db, family_id)
    # Read under the lock, so a request that deleted it a moment ago is seen as "not found", not as a stale row
    category = get_family_category(db, family_id, category_id)
    if category is None:
        db.rollback()
        raise _not_found()
    if cleaned is not None and name_is_taken(db, family_id, cleaned, except_id=category.id):
        db.rollback()
        raise _duplicate()
    category = update_category(db, category, cleaned, group_id)
    return _out(category, group_name_of(db, category))


def _in_use(used: int) -> HTTPException:
    if used == 1:
        detail = "Esta categoria é usada por 1 transação. Mude a categoria dela ou apague-a antes."
    else:
        detail = f"Esta categoria é usada por {used} transações. Mude a categoria delas ou apague-as antes."
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def delete_family_category(db: Session, family_id: UUID, category_id: UUID) -> dict:
    lock_family(db, family_id)
    category = get_family_category(db, family_id, category_id)
    if category is None:
        db.rollback()
        raise _not_found()
    used = count_transactions_using(db, category.id)
    if used:
        db.rollback()
        raise _in_use(used)
    try:
        delete_category(db, category)
    except IntegrityError:
        # A transaction took the category between the count and the delete (it does not take the family lock):
        # the database refused, and that is the same answer as "in use"
        db.rollback()
        raise _in_use(max(count_transactions_using(db, category_id), 1))
    return {"message": "Categoria apagada"}

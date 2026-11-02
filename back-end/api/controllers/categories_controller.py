from sqlalchemy.orm import Session

from api.repositories.categories_repo import get_all_categories as get_all_categories_repo


def get_all_categories(db: Session, family_id: int):
    return get_all_categories_repo(db, family_id)

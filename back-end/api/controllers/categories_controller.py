from sqlalchemy.orm import Session

from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
from api.repositories.categories_repo import get_all_groups as get_all_groups_repo


def get_all_categories(db: Session, family_id: int):
    return [
        {
            "id": category.id,
            "family_id": category.family_id,
            "name": category.name,
            "group_id": category.group_id,
            "group_name": group_name,
        }
        for category, group_name in get_all_categories_repo(db, family_id)
    ]


def get_all_groups(db: Session):
    return [{"id": group.id, "name": group.name} for group in get_all_groups_repo(db)]

from api.repositories.categories_repo import get_all_categories as get_all_categories_repo
 
from sqlalchemy.orm import Session

def get_all_categories(db: Session):
    return get_all_categories_repo(db)
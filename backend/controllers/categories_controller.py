from repositories.categories_repo import get_all_categories_repo
from fastapi.encoders import jsonable_encoder

def organize_categories_ctrl():
    categories = get_all_categories_repo()
    json_result = jsonable_encoder(categories)

    return json_result
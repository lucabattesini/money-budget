from repositories.categories_repo import get_all_categories_repo

def organize_categories_ctrl():
    categories = get_all_categories_repo()

    return categories
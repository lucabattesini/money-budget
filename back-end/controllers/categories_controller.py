from repositories.categories_repo import get_all_categories as get_all_categories_repo
 
def get_all_categories():
    categories = get_all_categories_repo()

    return categories
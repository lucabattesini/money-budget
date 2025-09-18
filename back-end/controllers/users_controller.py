from datetime import datetime
from repositories.users_repo import create_user_repo, user_login_repo, get_all_users as get_all_users_repo
from schemas.tables_schemas import User
 
def get_all_users():
    return get_all_users_repo()

def create_user_ctrl(user: User):
    today = datetime.now()
    user.last_login = today
    return create_user_repo(user)
 
def user_login_ctrl(email, password):
    logged_user = user_login_repo(email, password)
    return logged_user
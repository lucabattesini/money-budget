from datetime import datetime
from repositories.users_repo import create_user_repo, user_login_repo

def create_user_ctrl(name, email, password):
    today = datetime.now()
    created_user = create_user_repo(name, email, password, today, today, None, False)
    return created_user

def user_login_ctrl(email, password):
    logged_user = user_login_repo(email, password)
    return logged_user
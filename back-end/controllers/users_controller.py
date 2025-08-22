from datetime import datetime
from repositories.users_repo import create_user

def create_user_ctrl(name, email, password):
    today = datetime.now()
    created_user = create_user(name, email, password, today, today, None, False)
    return created_user
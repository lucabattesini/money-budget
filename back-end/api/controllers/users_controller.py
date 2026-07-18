from api.repositories.users_repo import upsert_user_repo, get_user_by_google_id_repo, get_user_by_id_repo

def upsert_user_ctrl(google_id, name, email, picture=None):
    """Create or update a user after Google OAuth login."""
    return upsert_user_repo(google_id, name, email, picture)

def get_user_by_google_id_ctrl(google_id):
    return get_user_by_google_id_repo(google_id)

def get_user_by_id_ctrl(user_id: int):
    return get_user_by_id_repo(user_id)

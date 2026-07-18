import os
import jwt
from datetime import datetime, timedelta, timezone
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from controllers.users_controller import upsert_user_ctrl

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return its payload."""
    payload = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    return payload


def create_jwt(user_id: int) -> str:
    """Generate a signed JWT for the given user_id."""
    expiry = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"user_id": user_id, "exp": expiry}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def login_with_google(id_token_str: str) -> dict:
    """
    Full Google login flow:
    1. Verify the Google ID token
    2. Upsert the user in the DB (via users_controller)
    3. Return a JWT + user data
    """
    google_payload = verify_google_token(id_token_str)

    google_id = google_payload["sub"]
    name = google_payload.get("name", "")
    email = google_payload.get("email", "")
    picture = google_payload.get("picture", None)

    user = upsert_user_ctrl(google_id, name, email, picture)

    token = create_jwt(user.id)

    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "picture": user.picture,
            "whatsapp_phone": user.whatsapp_phone,
        }
    }

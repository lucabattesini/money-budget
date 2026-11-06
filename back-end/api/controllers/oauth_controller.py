"""The sign-in of AI apps (the Claude connector, TKT-72): OAuth 2.1 with PKCE, in front of the existing Google login.

The person signs in on our own web page as always; this only lets them pass the sign-in on to an app, which then gets
its own tokens. Those tokens are random (not the app's login token), are kept as hashes, belong to one person, work only
on the connector and can be revoked at any time by deleting the connection.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy.orm import Session

from api.repositories.oauth_repo import (
    create_client,
    create_code,
    create_grant,
    delete_expired_codes,
    delete_expired_grants,
    delete_grant,
    delete_grant_by_hash,
    delete_unused_clients,
    get_client,
    get_grant_by_access,
    get_grant_by_refresh,
    list_grants_of,
    take_code,
    touch_grant,
)
from api.utils.clock import utc_now
from schemas.tables import OAuthClient, OAuthGrant

CODE_MINUTES = 5
ACCESS_HOURS = 1
REFRESH_DAYS = 30
UNUSED_CLIENT_DAYS = 1
MAX_REDIRECT_URIS = 5
MAX_URI_LENGTH = 500
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")


class OAuthError(Exception):
    """An error in the words of the OAuth standard (`error`), with a sentence for people."""

    def __init__(self, error: str, description: str, status_code: int = 400):
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code


def _now() -> datetime:
    return utc_now().replace(tzinfo=None)  # the database keeps UTC without a timezone


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _random_secret() -> str:
    return secrets.token_urlsafe(32)


def _redirect_uri_problem(uri) -> str | None:
    if not isinstance(uri, str) or not uri or len(uri) > MAX_URI_LENGTH:
        return "redirect_uris must be addresses of at most 500 characters"
    parts = urlsplit(uri)
    if parts.fragment or not parts.netloc:
        return "a redirect_uri must be a full address without a fragment"
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        return "a redirect_uri must use https (http only for localhost)"
    return None


def register_client(db: Session, name, redirect_uris) -> dict:
    """Dynamic client registration (RFC 7591), for public clients only."""
    if not isinstance(redirect_uris, list) or not redirect_uris or len(redirect_uris) > MAX_REDIRECT_URIS:
        raise OAuthError("invalid_redirect_uri", "redirect_uris must be a list of 1 to 5 addresses")
    for uri in redirect_uris:
        problem = _redirect_uri_problem(uri)
        if problem:
            raise OAuthError("invalid_redirect_uri", problem)
    name = name.strip()[:100] if isinstance(name, str) and name.strip() else "AI app"
    delete_unused_clients(db, _now() - timedelta(days=UNUSED_CLIENT_DAYS))
    client = create_client(db, name, list(dict.fromkeys(redirect_uris)))
    db.commit()
    return {
        "client_id": str(client.id),
        "client_name": client.name,
        "redirect_uris": client.redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


def _parse_id(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def check_authorization_request(
    db: Session, client_id, redirect_uri, response_type, code_challenge, code_challenge_method
) -> OAuthClient:
    """The app that is asking, if the request is one we can answer. Raises OAuthError otherwise. These errors are
    shown to the person and never sent to the redirect address, which is not trusted until it matches a registration."""
    client = get_client(db, parsed) if (parsed := _parse_id(client_id)) else None
    if client is None:
        raise OAuthError("invalid_request", "This app is not registered.")
    if redirect_uri not in client.redirect_uris:
        raise OAuthError("invalid_request", "The return address does not match the app's registration.")
    if response_type != "code":
        raise OAuthError("unsupported_response_type", "Only response_type=code is supported.")
    if code_challenge_method != "S256" or not code_challenge or len(code_challenge) > 128:
        raise OAuthError("invalid_request", "PKCE with code_challenge_method=S256 is required.")
    return client


def _back_to_app(redirect_uri: str, **params: str) -> str:
    parts = urlsplit(redirect_uri)
    query = parse_qsl(parts.query) + [(k, v) for k, v in params.items() if v]
    return urlunsplit(parts._replace(query=urlencode(query)))


def decide(
    db: Session,
    user_id: UUID,
    client_id,
    redirect_uri,
    response_type,
    code_challenge,
    code_challenge_method,
    state: str,
    allow: bool,
) -> str:
    """The person's answer. Returns the address to send them to: back to the app, with a code or with an error."""
    client = check_authorization_request(
        db, client_id, redirect_uri, response_type, code_challenge, code_challenge_method
    )
    if not allow:
        return _back_to_app(redirect_uri, error="access_denied", state=state)
    code = _random_secret()
    delete_expired_codes(db, _now())
    create_code(
        db,
        hash_secret(code),
        client.id,
        user_id,
        redirect_uri,
        code_challenge,
        _now() + timedelta(minutes=CODE_MINUTES),
    )
    db.commit()
    return _back_to_app(redirect_uri, code=code, state=state)


def _new_tokens(db: Session, grant: OAuthGrant | None, client_id: UUID, user_id: UUID) -> dict:
    access, refresh = _random_secret(), _random_secret()
    now = _now()
    values = (
        hash_secret(access),
        now + timedelta(hours=ACCESS_HOURS),
        hash_secret(refresh),
        now + timedelta(days=REFRESH_DAYS),
    )
    if grant is None:
        create_grant(db, client_id, user_id, values[0], values[1], values[2], values[3])
    else:  # refreshing replaces both tokens: the old refresh token stops working
        grant.access_hash, grant.access_expires_at, grant.refresh_hash, grant.refresh_expires_at = values
    delete_expired_grants(db, now)
    db.commit()
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": ACCESS_HOURS * 3600,
        "refresh_token": refresh,
    }


def _pkce_matches(verifier: str, challenge: str) -> bool:
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(digest, challenge)


def exchange_token(db: Session, form: dict) -> dict:
    client = get_client(db, parsed) if (parsed := _parse_id(form.get("client_id"))) else None
    if client is None:
        raise OAuthError("invalid_client", "This app is not registered.", 401)
    grant_type = form.get("grant_type")
    if grant_type == "authorization_code":
        code = take_code(db, hash_secret(form.get("code") or ""))
        # taken (and so spent) before it is checked: a wrong try costs the code
        db.commit()
        verifier = form.get("code_verifier") or ""
        if (
            code is None
            or code.expires_at < _now()
            or code.client_id != client.id
            or code.redirect_uri != form.get("redirect_uri")
            or not (43 <= len(verifier) <= 128)
            or not _pkce_matches(verifier, code.code_challenge)
        ):
            raise OAuthError("invalid_grant", "The code is wrong, expired or already used.")
        return _new_tokens(db, None, client.id, code.user_id)
    if grant_type == "refresh_token":
        grant = get_grant_by_refresh(db, hash_secret(form.get("refresh_token") or ""))
        if grant is None or grant.client_id != client.id or grant.refresh_expires_at < _now():
            db.rollback()
            raise OAuthError("invalid_grant", "The refresh token is wrong, expired or revoked.")
        return _new_tokens(db, grant, client.id, grant.user_id)
    raise OAuthError("unsupported_grant_type", "Use authorization_code or refresh_token.")


def revoke_token(db: Session, token: str, client_id) -> None:
    """RFC 7009: forgetting a token that is not known is not an error."""
    parsed = _parse_id(client_id)
    if parsed is not None and token:
        delete_grant_by_hash(db, hash_secret(token), parsed)
        db.commit()


def authenticate_access_token(db: Session, token: str) -> OAuthGrant | None:
    """The connection an access token belongs to, if it is known and not expired."""
    grant = get_grant_by_access(db, hash_secret(token)) if token else None
    now = _now()
    if grant is None or grant.access_expires_at < now:
        return None
    touch_grant(db, grant, now)
    return grant


def list_connections(db: Session, user_id: UUID) -> list[dict]:
    return [
        {"id": grant.id, "app": name, "connected_at": grant.created_at, "last_used_at": grant.last_used_at}
        for grant, name in list_grants_of(db, user_id, _now())
    ]


def disconnect(db: Session, user_id: UUID, grant_id: UUID) -> bool:
    """Revoke a connection of the person's own. False if they have no such connection."""
    removed = delete_grant(db, grant_id, user_id)
    db.commit()
    return removed

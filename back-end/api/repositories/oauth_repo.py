from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from schemas.tables import OAuthClient, OAuthCode, OAuthGrant


def create_client(db: Session, name: str, redirect_uris: list[str]) -> OAuthClient:
    client = OAuthClient(name=name, redirect_uris=redirect_uris)
    db.add(client)
    db.flush()
    return client


def get_client(db: Session, client_id: UUID) -> OAuthClient | None:
    return db.get(OAuthClient, client_id)


def delete_unused_clients(db: Session, older_than: datetime) -> None:
    """Registration is open to anyone, so the apps nobody ever signed in with are forgotten after a while."""
    used = db.query(OAuthGrant.client_id).union(db.query(OAuthCode.client_id))
    db.query(OAuthClient).filter(OAuthClient.created_at < older_than, OAuthClient.id.not_in(used)).delete(
        synchronize_session=False
    )


def create_code(
    db: Session, code_hash: str, client_id: UUID, user_id: UUID, redirect_uri: str, challenge: str, expires_at: datetime
) -> None:
    db.add(
        OAuthCode(
            code_hash=code_hash,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            expires_at=expires_at,
        )
    )


def take_code(db: Session, code_hash: str) -> OAuthCode | None:
    """The code, removed in the same step: a code works once, even if two requests bring it at the same time."""
    code = db.query(OAuthCode).filter(OAuthCode.code_hash == code_hash).with_for_update().first()
    if code is not None:
        db.delete(code)
        db.flush()
    return code


def delete_expired_codes(db: Session, now: datetime) -> None:
    db.query(OAuthCode).filter(OAuthCode.expires_at < now).delete(synchronize_session=False)


def create_grant(
    db: Session,
    client_id: UUID,
    user_id: UUID,
    access_hash: str,
    access_expires_at: datetime,
    refresh_hash: str,
    refresh_expires_at: datetime,
) -> OAuthGrant:
    grant = OAuthGrant(
        client_id=client_id,
        user_id=user_id,
        access_hash=access_hash,
        access_expires_at=access_expires_at,
        refresh_hash=refresh_hash,
        refresh_expires_at=refresh_expires_at,
    )
    db.add(grant)
    db.flush()
    return grant


def get_grant_by_access(db: Session, access_hash: str) -> OAuthGrant | None:
    return db.query(OAuthGrant).filter(OAuthGrant.access_hash == access_hash).first()


def get_grant_by_refresh(db: Session, refresh_hash: str) -> OAuthGrant | None:
    return db.query(OAuthGrant).filter(OAuthGrant.refresh_hash == refresh_hash).with_for_update().first()


def touch_grant(db: Session, grant: OAuthGrant, now: datetime) -> None:
    """Note that the connection was used, at most once a minute (every call would be a write)."""
    if grant.last_used_at is None or now - grant.last_used_at > timedelta(minutes=1):
        grant.last_used_at = now
        db.commit()


def list_grants_of(db: Session, user_id: UUID, now: datetime) -> list[tuple[OAuthGrant, str]]:
    """The person's connections that still work, each with the name of the app."""
    return (
        db.query(OAuthGrant, OAuthClient.name)
        .join(OAuthClient, OAuthGrant.client_id == OAuthClient.id)
        .filter(OAuthGrant.user_id == user_id, OAuthGrant.refresh_expires_at > now)
        .order_by(OAuthGrant.created_at.desc(), OAuthGrant.id)
        .all()
    )


def delete_grant(db: Session, grant_id: UUID, user_id: UUID) -> bool:
    return (
        db.query(OAuthGrant)
        .filter(OAuthGrant.id == grant_id, OAuthGrant.user_id == user_id)
        .delete(synchronize_session=False)
        > 0
    )


def delete_grant_by_hash(db: Session, token_hash: str, client_id: UUID) -> None:
    db.query(OAuthGrant).filter(
        OAuthGrant.client_id == client_id,
        (OAuthGrant.access_hash == token_hash) | (OAuthGrant.refresh_hash == token_hash),
    ).delete(synchronize_session=False)


def delete_expired_grants(db: Session, now: datetime) -> None:
    db.query(OAuthGrant).filter(OAuthGrant.refresh_expires_at < now).delete(synchronize_session=False)

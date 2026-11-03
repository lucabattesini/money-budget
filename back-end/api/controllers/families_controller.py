import hashlib
import re
import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repositories.families_repo import (
    HasOtherMembers,
    InvalidInvite,
    NothingToReturnTo,
    OwnerCannotLeave,
    SameFamily,
    TooManyInvites,
    cancel_invite,
    create_invite,
    join_family,
    list_active_invites,
    list_members,
    purge_abandoned_families,
    return_deadline,
    return_to_previous_family,
)
from schemas.tables import Users

# No 0/O/1/I/L: codes are read aloud and typed by hand. 16 characters of 31 are far too many to guess.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 16
MAX_ACTIVE_INVITES = 3


def _normalize(code: str) -> str:
    """What a person typed, as the code it stands for: no dashes or spaces, any case."""
    return re.sub(r"[^A-Za-z0-9]", "", code or "").upper()


def _hash(code: str) -> str:
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def _display(code: str) -> str:
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def _only_owner(user: Users) -> None:
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Só quem criou a família pode convidar.")


def get_my_family(db: Session, user: Users) -> dict:
    deadline = return_deadline(db, user)
    return {
        "id": user.family_id,
        "role": user.role,
        # Set while the person can still go back to the family they left (they started empty when joining)
        "previous_family": None if deadline is None else {"available_until": deadline},
        "members": [
            {"id": m.id, "name": m.name, "picture": m.picture, "role": m.role} for m in list_members(db, user.family_id)
        ],
    }


def _invite_out(invite) -> dict:
    return {
        "id": invite.id,
        "code_hint": invite.code_hint,
        "created_at": invite.created_at,
        "expires_at": invite.expires_at,
    }


def create_family_invite(db: Session, user: Users) -> dict:
    """A new code for the family. The code is returned here and never again: only its hash is kept."""
    _only_owner(user)
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    try:
        invite = create_invite(db, user.family_id, user.id, _hash(code), code[-4:], MAX_ACTIVE_INVITES)
    except TooManyInvites:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Você já tem {MAX_ACTIVE_INVITES} códigos ativos. Cancele algum antes.",
        )
    return {**_invite_out(invite), "code": _display(code)}


def list_family_invites(db: Session, user: Users) -> list[dict]:
    _only_owner(user)
    return [_invite_out(i) for i in list_active_invites(db, user.family_id)]


def cancel_family_invite(db: Session, user: Users, invite_id: int) -> dict:
    _only_owner(user)
    # Missing, already used, expired and another family's all look the same
    if not cancel_invite(db, user.family_id, invite_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código não encontrado.")
    return {"message": "Código cancelado"}


def join_with_code(db: Session, user: Users, code: str, bring_data: bool) -> dict:
    purge_abandoned_families(db)  # like export files: old leftovers are cleaned whenever someone moves
    try:
        join_family(db, user, _hash(code), bring_data)
    except InvalidInvite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código inválido, expirado ou já usado.")
    except HasOtherMembers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já faz parte de uma família com outras pessoas. Saia dela ou passe a posse antes de entrar em outra.",
        )
    except SameFamily:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já faz parte dessa família.")
    return get_my_family(db, user)


def go_back_to_previous_family(db: Session, user: Users) -> dict:
    try:
        return_to_previous_family(db, user)
    except NothingToReturnTo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Não há uma família anterior para voltar, ou o prazo acabou."
        )
    except OwnerCannotLeave:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você é dono de uma família com outras pessoas. Passe a posse antes de sair dela.",
        )
    return get_my_family(db, user)

import unicodedata
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from schemas.tables import Categories, Families, FamilyInvites, TransactionDB, Users

INVITE_LIFETIME = timedelta(days=7)  # asked of the database clock, like the export times


class InvalidInvite(Exception):
    """The code does not exist, was already used, or has expired (the caller cannot tell which)."""


class HasOtherMembers(Exception):
    """The person is in a family with other people, so they cannot move to another one."""


class SameFamily(Exception):
    """The code is for the family the person is already in."""


def list_members(db: Session, family_id: int) -> list[Users]:
    return db.query(Users).filter(Users.family_id == family_id).order_by(Users.id).all()


def count_active_invites(db: Session, family_id: int) -> int:
    return _active(db.query(FamilyInvites).filter(FamilyInvites.family_id == family_id)).count()


def _active(query):
    return query.filter(FamilyInvites.used_at.is_(None), FamilyInvites.expires_at > func.now())


def create_invite(db: Session, family_id: int, user_id: int, code_hash: str, code_hint: str) -> FamilyInvites:
    invite = FamilyInvites(
        family_id=family_id,
        created_by=user_id,
        code_hash=code_hash,
        code_hint=code_hint,
        expires_at=func.now() + INVITE_LIFETIME,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def list_active_invites(db: Session, family_id: int) -> list[FamilyInvites]:
    query = db.query(FamilyInvites).filter(FamilyInvites.family_id == family_id)
    return _active(query).order_by(FamilyInvites.id.desc()).all()


def cancel_invite(db: Session, family_id: int, invite_id: int) -> bool:
    """Delete one of the family's codes that can still be used. False if there is none."""
    query = db.query(FamilyInvites).filter(FamilyInvites.id == invite_id, FamilyInvites.family_id == family_id)
    deleted = _active(query).delete(synchronize_session=False)
    db.commit()
    return deleted > 0


def _fold(name: str | None) -> str:
    """A name without case, accents or surrounding spaces, so "Alimentação" and " alimentacao" match."""
    decomposed = unicodedata.normalize("NFKD", (name or "").strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _bring_data(db: Session, old_family_id: int, new_family_id: int) -> None:
    """Move the family's transactions and categories to the new family.

    A category whose name matches one the new family already has is merged into it: its transactions are
    re-pointed and it is deleted. The others come along as they are. Default categories belong to nobody
    and are never touched.
    """
    kept = {_fold(c.name): c for c in db.query(Categories).filter(Categories.family_id == new_family_id)}
    db.query(TransactionDB).filter(TransactionDB.family_id == old_family_id).update(
        {TransactionDB.family_id: new_family_id}, synchronize_session=False
    )
    for category in db.query(Categories).filter(Categories.family_id == old_family_id).order_by(Categories.id):
        target = kept.get(_fold(category.name))
        if target is None:
            category.family_id = new_family_id
            kept[_fold(category.name)] = category
        else:
            db.query(TransactionDB).filter(TransactionDB.category_id == category.id).update(
                {TransactionDB.category_id: target.id}, synchronize_session=False
            )
            db.delete(category)


def join_family(db: Session, user: Users, code_hash: str, bring_data: bool) -> None:
    """Move `user` into the family the code belongs to. Everything happens in one database transaction.

    Either all of it is done (the code is used up, the person changes family, their data moves if asked) or
    none of it is. The code is claimed while holding a lock on its row, so two people cannot use it at once.
    """
    old_family_id = user.family_id
    try:
        # Lock the family being left, so nobody joins it while we count its people
        db.query(Families).filter(Families.id == old_family_id).with_for_update().one()
        if db.query(Users.id).filter(Users.family_id == old_family_id).count() > 1:
            raise HasOtherMembers()

        invite = _active(db.query(FamilyInvites).filter(FamilyInvites.code_hash == code_hash).with_for_update()).first()
        if invite is None:
            raise InvalidInvite()
        if invite.family_id == old_family_id:
            raise SameFamily()

        invite.used_by = user.id
        invite.used_at = func.now()
        if bring_data:
            _bring_data(db, old_family_id, invite.family_id)
        # The family being left is now empty: its codes must not let a stranger into the data left there
        db.query(FamilyInvites).filter(
            FamilyInvites.family_id == old_family_id, FamilyInvites.used_at.is_(None)
        ).delete(synchronize_session=False)
        user.family_id = invite.family_id
        user.role = "member"
        db.commit()
    except Exception:
        db.rollback()
        raise

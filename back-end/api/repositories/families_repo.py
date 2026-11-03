import unicodedata
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.utils.category_names import plain_name
from schemas.tables import (
    Budgets,
    Categories,
    ExportJobDB,
    Families,
    FamilyInvites,
    ImportJobDB,
    TransactionDB,
    Users,
)

INVITE_LIFETIME = timedelta(days=7)  # asked of the database clock, like the export times
ABANDONED_KEPT_FOR = timedelta(days=30)  # how long a family nobody is in is kept, in case someone goes back


class InvalidInvite(Exception):
    """The code does not exist, was already used, or has expired (the caller cannot tell which)."""


class HasOtherMembers(Exception):
    """The person is in a family with other people, so they cannot move to another one."""


class SameFamily(Exception):
    """The code is for the family the person is already in."""


class TooManyInvites(Exception):
    """The family already has the most active codes it may have."""


class NothingToReturnTo(Exception):
    """There is no previous family to go back to (none, brought along, expired or no longer empty)."""


class OwnerCannotLeave(Exception):
    """The person owns a family with other people in it, so they cannot walk out of it."""


def get_family(db: Session, family_id: int) -> Families:
    return db.query(Families).filter(Families.id == family_id).one()


def update_settings(db: Session, family_id: int, currency: str | None, language: str | None) -> Families:
    """Change the family's currency and/or language (a value left as None keeps its current one)."""
    family = db.query(Families).filter(Families.id == family_id).with_for_update().one()
    if currency is not None:
        family.currency = currency
    if language is not None:
        family.language = language
    db.commit()
    return family


def list_members(db: Session, family_id: int) -> list[Users]:
    return db.query(Users).filter(Users.family_id == family_id).order_by(Users.id).all()


def count_active_invites(db: Session, family_id: int) -> int:
    return _active(db.query(FamilyInvites).filter(FamilyInvites.family_id == family_id)).count()


def _active(query):
    return query.filter(FamilyInvites.used_at.is_(None), FamilyInvites.expires_at > func.now())


def create_invite(
    db: Session, family_id: int, user_id: int, code_hash: str, code_hint: str, max_active: int
) -> FamilyInvites:
    """Add a code to the family. The family row is locked while counting, so two requests cannot both fit the last place."""
    db.query(Families).filter(Families.id == family_id).with_for_update().one()
    if count_active_invites(db, family_id) >= max_active:
        db.rollback()
        raise TooManyInvites()
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
    """A name without emoji, case, accents or surrounding spaces, so "🍽️ Alimentação" and " alimentacao" match."""
    decomposed = unicodedata.normalize("NFKD", plain_name(name))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _bring_data(db: Session, old_family_id: int, new_family_id: int) -> None:
    """Move the family's transactions and categories to the new family. Budgets are not brought: a plan belongs to
    the family that made it, so the ones of the family being left are deleted and the new family keeps its own.

    A category whose name matches one the new family already has is merged into it: its transactions are
    re-pointed and it is deleted. The others come along as they are. Default categories belong to nobody
    and are never touched.
    """
    # Before any category is deleted below: a budget points at its category
    db.query(Budgets).filter(Budgets.family_id == old_family_id).delete(synchronize_session=False)
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


def _lock_families(db: Session, *family_ids: int) -> dict[int, Families]:
    """Lock families in id order, always, so two people moving at once cannot wait on each other forever."""
    rows = db.query(Families).filter(Families.id.in_(family_ids)).order_by(Families.id).with_for_update().all()
    return {f.id: f for f in rows}


def _member_count(db: Session, family_id: int) -> int:
    return db.query(Users.id).filter(Users.family_id == family_id).count()


def _lock_user(db: Session, user: Users) -> None:
    """Lock the person's own row and re-read it, so two requests from the same person cannot both move them."""
    db.refresh(user, with_for_update=True)


def join_family(db: Session, user: Users, code_hash: str, bring_data: bool) -> None:
    """Move `user` into the family the code belongs to. Everything happens in one database transaction.

    Either all of it is done (the code is used up, the person changes family, their data moves if asked) or
    none of it is. Locks are taken in a fixed order (the person, both families by id, the code), so the code
    cannot be used twice at once and nobody can join a family while its only person is walking out of it.

    The family left behind is marked abandoned. With `bring_data` false its data stays there and the person
    can go back for ABANDONED_KEPT_FOR; with it true there is nothing to go back to.
    """
    try:
        _lock_user(db, user)
        old_family_id = user.family_id
        peek = _active(db.query(FamilyInvites).filter(FamilyInvites.code_hash == code_hash)).first()
        if peek is None:
            raise InvalidInvite()
        families = _lock_families(db, old_family_id, peek.family_id)

        if _member_count(db, old_family_id) > 1:
            raise HasOtherMembers()
        invite = _active(db.query(FamilyInvites).filter(FamilyInvites.code_hash == code_hash).with_for_update()).first()
        if invite is None or _member_count(db, invite.family_id) == 0:
            raise InvalidInvite()  # used, cancelled or expired meanwhile, or its family was just left by its only person
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
        families[old_family_id].abandoned_at = func.now()
        user.previous_family_id = None if bring_data else old_family_id
        user.family_id = invite.family_id
        user.role = "member"
        db.commit()
    except Exception:
        db.rollback()
        raise


def return_deadline(db: Session, user: Users) -> datetime | None:
    """Until when the person can go back to the family they left, or None if they cannot."""
    if user.previous_family_id is None:
        return None
    abandoned_at = (
        db.query(Families.abandoned_at)
        .filter(Families.id == user.previous_family_id, Families.abandoned_at > func.now() - ABANDONED_KEPT_FOR)
        .scalar()
    )
    return None if abandoned_at is None else abandoned_at + ABANDONED_KEPT_FOR


def return_to_previous_family(db: Session, user: Users) -> None:
    """Go back to the family left behind. What was entered in the family being left stays in it."""
    try:
        _lock_user(db, user)
        previous_id, current_id = user.previous_family_id, user.family_id
        if previous_id is None:
            raise NothingToReturnTo()
        families = _lock_families(db, previous_id, current_id)
        if return_deadline(db, user) is None or _member_count(db, previous_id) > 0:
            raise NothingToReturnTo()
        if user.role == "owner" and _member_count(db, current_id) > 1:
            raise OwnerCannotLeave()

        user.family_id = previous_id
        user.role = "owner"
        user.previous_family_id = None
        families[previous_id].abandoned_at = None
        db.flush()
        if _member_count(db, current_id) == 0:  # the family just left has nobody now: it is abandoned too
            families[current_id].abandoned_at = func.now()
            db.query(FamilyInvites).filter(
                FamilyInvites.family_id == current_id, FamilyInvites.used_at.is_(None)
            ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise


def purge_abandoned_families(db: Session) -> None:
    """Delete, for good, every family nobody has been in for ABANDONED_KEPT_FOR, with everything it holds.

    Only families with no one in them are touched, whatever their date says.
    """
    ids = [
        row.id
        for row in db.query(Families.id).filter(
            Families.abandoned_at < func.now() - ABANDONED_KEPT_FOR,
            ~db.query(Users.id).filter(Users.family_id == Families.id).exists(),
        )
    ]
    if not ids:
        return
    category_ids = db.query(Categories.id).filter(Categories.family_id.in_(ids))
    # Nobody else's transaction may point at a category that is about to go
    db.query(TransactionDB).filter(TransactionDB.category_id.in_(category_ids)).update(
        {TransactionDB.category_id: None}, synchronize_session=False
    )
    db.query(TransactionDB).filter(TransactionDB.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(Budgets).filter(Budgets.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(Categories).filter(Categories.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(ExportJobDB).filter(ExportJobDB.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(ImportJobDB).filter(ImportJobDB.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(FamilyInvites).filter(FamilyInvites.family_id.in_(ids)).delete(synchronize_session=False)
    db.query(Users).filter(Users.previous_family_id.in_(ids)).update(
        {Users.previous_family_id: None}, synchronize_session=False
    )
    db.query(Families).filter(Families.id.in_(ids)).delete(synchronize_session=False)
    db.commit()

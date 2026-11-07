from datetime import datetime, time, timedelta
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from api.repositories.categories_repo import category_visible_to_family
from api.utils.totals import excluded_by_default
from schemas.tables import Categories, Merchants, TransactionDB, Users
from schemas.tables_schemas import (
    Transaction,
    TransactionAggregate,
    TransactionBulkUpdate,
    TransactionFilters,
    TransactionOut,
    TransactionUpdate,
)

MAX_LIST_LIMIT = 200

ORDER_COLUMNS = {
    "date": TransactionDB.transactioned_at,
    "value": TransactionDB.value,
}

PERIOD_PARTS = {
    "year": ("year",),
    "month": ("year", "month"),
    "day": ("year", "month", "day"),
}

GroupBy = Literal["category", "merchant", "day", "month", "year", "weekday"]


def create_transaction(db: Session, t: Transaction, family_id: UUID, user_id: UUID, merchant_id: Optional[UUID] = None):
    try:
        data = t.model_dump(exclude={"merchant"})
        data["merchant_id"] = merchant_id
        if (
            data["excluded"] is None
        ):  # not said: a transfer or a card payment is left out of the totals, the rest counts
            data["excluded"] = t.category_id in excluded_by_default(db, [t.category_id])
        if data["user_id"] is None:
            data["user_id"] = user_id  # belongs to whoever adds it unless said otherwise
        transaction = TransactionDB(**data, family_id=family_id)
        db.add(transaction)
        db.commit()
        return t
    except Exception:
        db.rollback()
        raise


def get_transactions(db: Session, start: Optional[datetime], end: Optional[datetime], family_id: UUID):
    """The family's transactions, newest first. start is included and end excluded; None means open."""
    query = db.query(TransactionDB).filter(TransactionDB.family_id == family_id)
    if start is not None:
        query = query.filter(TransactionDB.transactioned_at >= start)
    if end is not None:
        query = query.filter(TransactionDB.transactioned_at < end)
    return query.order_by(TransactionDB.transactioned_at.desc()).all()


def get_transactions_summed_by_category(
    db: Session, start: Optional[datetime], end: Optional[datetime], family_id: UUID
):
    query = (
        db.query(TransactionDB.category_id, func.sum(TransactionDB.value).label("total"))
        # spending only, and not what the person left out of the totals
        .filter(TransactionDB.family_id == family_id, TransactionDB.type == "debit", TransactionDB.excluded.is_(False))
        .group_by(TransactionDB.category_id)
    )

    if start is not None:
        query = query.filter(TransactionDB.transactioned_at >= start)
    if end is not None:
        query = query.filter(TransactionDB.transactioned_at < end)

    return query.all()


def _apply_filters(query, family_id: UUID, f: TransactionFilters, counted_only: bool = False):
    """Scope the query to the family and apply every filter that was set. `counted_only` leaves out the transactions
    the person excluded from the totals: every sum asks for it, a plain list does not."""
    query = query.filter(TransactionDB.family_id == family_id)
    if counted_only:
        query = query.filter(TransactionDB.excluded.is_(False))

    if f.start_date:
        query = query.filter(TransactionDB.transactioned_at >= datetime.combine(f.start_date, time.min))
    if f.end_date:
        # Half-open range so the whole end day is included
        query = query.filter(
            TransactionDB.transactioned_at < datetime.combine(f.end_date + timedelta(days=1), time.min)
        )
    if f.category_ids:
        query = query.filter(TransactionDB.category_id.in_(f.category_ids))
    if f.exclude_category_ids:
        query = query.filter(TransactionDB.category_id.not_in(f.exclude_category_ids))
    if f.merchant_ids:
        query = query.filter(TransactionDB.merchant_id.in_(f.merchant_ids))
    if f.search:
        query = query.filter(TransactionDB.label.icontains(f.search, autoescape=True))
    if f.min_value is not None:
        query = query.filter(TransactionDB.value >= f.min_value)
    if f.max_value is not None:
        query = query.filter(TransactionDB.value <= f.max_value)
    if f.weekdays:
        query = query.filter(extract("dow", TransactionDB.transactioned_at).in_(f.weekdays))

    return query


def list_transactions(
    db: Session,
    family_id: UUID,
    filters: TransactionFilters,
    order_by: Literal["date", "value"] = "date",
    order_dir: Literal["asc", "desc"] = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[TransactionOut]:
    order_column = ORDER_COLUMNS[order_by]
    order_column = order_column.asc() if order_dir == "asc" else order_column.desc()

    query = _with_names(db.query(TransactionDB, Categories.name, Users.name, Merchants.name))
    rows = (
        _apply_filters(query, family_id, filters)
        .order_by(order_column, TransactionDB.id.desc())
        .limit(max(1, min(limit, MAX_LIST_LIMIT)))
        .offset(max(0, offset))
        .all()
    )

    return _to_out(rows)


def list_all_transactions(db: Session, family_id: UUID) -> list[TransactionOut]:
    """Every transaction of the family, newest first. No page limit: meant for exports."""
    query = _with_names(db.query(TransactionDB, Categories.name, Users.name, Merchants.name))
    rows = (
        query.filter(TransactionDB.family_id == family_id)
        .order_by(TransactionDB.transactioned_at.desc(), TransactionDB.id.desc())
        .all()
    )
    return _to_out(rows)


def _with_names(query):
    """Add the category's and the person's name to a query of transactions."""
    return (
        query.outerjoin(Categories, TransactionDB.category_id == Categories.id)
        .outerjoin(Users, TransactionDB.user_id == Users.id)
        .outerjoin(Merchants, TransactionDB.merchant_id == Merchants.id)
    )


def _to_out(rows) -> list[TransactionOut]:
    return [
        TransactionOut(
            id=t.id,
            label=t.label,
            value=t.value,
            type=t.type,
            transactioned_at=t.transactioned_at,
            created_at=t.created_at,
            updated_at=t.updated_at,
            category_id=t.category_id,
            category_name=category_name,
            user_id=t.user_id,
            user_name=user_name,
            merchant_id=t.merchant_id,
            merchant_name=merchant_name,
            excluded=t.excluded,
        )
        for t, category_name, user_name, merchant_name in rows
    ]


def aggregate_transactions(
    db: Session,
    family_id: UUID,
    filters: TransactionFilters,
    group_by: Optional[GroupBy] = None,
) -> list[TransactionAggregate]:
    """Total, count, average and max value, optionally grouped. group_by=None returns a single overall row."""
    metrics = [
        func.coalesce(func.sum(TransactionDB.value), 0).label("total"),
        func.count(TransactionDB.id).label("count"),
        func.coalesce(func.avg(TransactionDB.value), 0).label("average"),
        func.coalesce(func.max(TransactionDB.value), 0).label("max"),
    ]

    if group_by is None:
        row = _apply_filters(db.query(*metrics), family_id, filters, counted_only=True).one()
        return [TransactionAggregate(**row._mapping)]

    if group_by == "category":
        keys = [TransactionDB.category_id.label("category_id"), Categories.name.label("category_name")]
        query = db.query(*keys, *metrics).outerjoin(Categories, TransactionDB.category_id == Categories.id)
        query = _apply_filters(query, family_id, filters, counted_only=True)
        query = query.group_by(*keys).order_by(func.sum(TransactionDB.value).desc())
        return [TransactionAggregate(**row._mapping) for row in query.all()]

    if group_by == "merchant":
        keys = [TransactionDB.merchant_id.label("merchant_id"), Merchants.name.label("merchant_name")]
        query = db.query(*keys, *metrics).outerjoin(Merchants, TransactionDB.merchant_id == Merchants.id)
        query = _apply_filters(query, family_id, filters, counted_only=True)
        query = query.group_by(*keys).order_by(func.sum(TransactionDB.value).desc())
        return [TransactionAggregate(**row._mapping) for row in query.all()]

    if group_by == "weekday":
        key = extract("dow", TransactionDB.transactioned_at).label("weekday")
        query = _apply_filters(db.query(key, *metrics), family_id, filters, counted_only=True)
        query = query.group_by(key).order_by(key)
        return [TransactionAggregate(**row._mapping) for row in query.all()]

    parts = [extract(p, TransactionDB.transactioned_at).label(p) for p in PERIOD_PARTS[group_by]]
    query = _apply_filters(db.query(*parts, *metrics), family_id, filters, counted_only=True)
    query = query.group_by(*parts).order_by(*parts)

    results = []
    for row in query.all():
        data = dict(row._mapping)
        period_values = [int(data.pop(p)) for p in PERIOD_PARTS[group_by]]
        data["period"] = "-".join(f"{v:02d}" for v in period_values)
        results.append(TransactionAggregate(**data))
    return results


def delete_transaction(db: Session, id, family_id: UUID):
    transaction = db.query(TransactionDB).filter_by(id=id, family_id=family_id).first()
    if transaction:
        db.delete(transaction)
        db.commit()
        return True
    return False


def category_exists(db: Session, category_id: UUID, family_id: UUID) -> bool:
    """True if the category is a default one or belongs to the family."""
    return category_visible_to_family(db, category_id, family_id)


def update_transaction(
    db: Session, id: UUID, family_id: UUID, changes: TransactionUpdate, merchant_id: Optional[UUID] = None
):
    """Update one of the family's transactions. Returns it, or None if it is missing or not the family's."""
    transaction = db.query(TransactionDB).filter_by(id=id, family_id=family_id).first()
    if transaction is None:
        return None
    transaction.label = changes.label
    transaction.value = changes.value
    transaction.category_id = changes.category_id
    if changes.type is not None:
        transaction.type = changes.type
    if changes.transactioned_at is not None:
        transaction.transactioned_at = changes.transactioned_at
    if changes.user_id is not None:
        transaction.user_id = changes.user_id
    if changes.merchant is not None:  # None keeps it; "" (merchant_id None) takes it off
        transaction.merchant_id = merchant_id
    if changes.excluded is not None:
        transaction.excluded = changes.excluded
    transaction.updated_at = datetime.now()
    db.commit()
    return transaction


def get_family_transactions_by_ids(db: Session, ids: list[UUID], family_id: UUID) -> list[TransactionDB]:
    """The family's transactions among `ids` (others, and other families', are simply not returned)."""
    return db.query(TransactionDB).filter(TransactionDB.family_id == family_id, TransactionDB.id.in_(set(ids))).all()


def bulk_update_transactions(
    db: Session,
    rows: list[TransactionDB],
    changes: TransactionBulkUpdate,
    merchant_id: Optional[UUID],
):
    """Apply the same changes to rows already checked to be the family's. All or none."""
    try:
        now = datetime.now()
        for t in rows:
            if changes.category_id is not None:
                t.category_id = changes.category_id
            if changes.user_id is not None:
                t.user_id = changes.user_id
            if changes.merchant is not None:  # "" (merchant_id None) takes it off
                t.merchant_id = merchant_id
            if changes.excluded is not None:
                t.excluded = changes.excluded
            t.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise


def bulk_delete_transactions(db: Session, rows: list[TransactionDB]):
    try:
        for t in rows:
            db.delete(t)
        db.commit()
    except Exception:
        db.rollback()
        raise


def find_duplicate_groups(db: Session, family_id: UUID, start_date, end_date, ignore_excluded=False) -> list[list[TransactionOut]]:
    """Groups of two or more transactions of the same day, amount and type, between the two days (both included).
    Oldest group first; inside a group, the one saved first comes first."""
    query = _with_names(db.query(TransactionDB, Categories.name, Users.name, Merchants.name))
    rows = _apply_filters(query, family_id, TransactionFilters(start_date=start_date, end_date=end_date)).all()
    groups: dict[tuple, list] = {}
    for row in rows:
        t = row[0]
        if ignore_excluded and t.excluded:
            continue
        groups.setdefault((t.transactioned_at.date(), t.value, t.type), []).append(row)
    result = []
    for key in sorted(k for k, v in groups.items() if len(v) > 1):
        members = sorted(groups[key], key=lambda r: (r[0].created_at is None, r[0].created_at, str(r[0].id)))
        result.append(_to_out(members))
    return result

from datetime import datetime, time, timedelta
from typing import Literal, Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from schemas.tables import Categories, TransactionDB
from schemas.tables_schemas import (
    Transaction,
    TransactionAggregate,
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

GroupBy = Literal["category", "day", "month", "year", "weekday"]


def create_transaction(db: Session, t: Transaction, user_id: int):
    try:
        transaction = TransactionDB(**t.dict(), user_id=user_id)
        db.add(transaction)
        db.commit()
        return t
    except Exception:
        db.rollback()
        raise


def get_transactions(db: Session, start: Optional[datetime], end: Optional[datetime], user_id: int):
    """The user's transactions, newest first. start is included and end excluded; None means open."""
    query = db.query(TransactionDB).filter(TransactionDB.user_id == user_id)
    if start is not None:
        query = query.filter(TransactionDB.transactioned_at >= start)
    if end is not None:
        query = query.filter(TransactionDB.transactioned_at < end)
    return query.order_by(TransactionDB.transactioned_at.desc()).all()


def get_transactions_summed_by_category(db: Session, start: Optional[datetime], end: Optional[datetime], user_id: int):
    query = (
        db.query(TransactionDB.category_id, func.sum(TransactionDB.value).label("total"))
        .filter(TransactionDB.user_id == user_id, TransactionDB.type == "debit")  # spending only
        .group_by(TransactionDB.category_id)
    )

    if start is not None:
        query = query.filter(TransactionDB.transactioned_at >= start)
    if end is not None:
        query = query.filter(TransactionDB.transactioned_at < end)

    return query.all()


def _apply_filters(query, user_id: int, f: TransactionFilters):
    """Scope the query to the user and apply every filter that was set."""
    query = query.filter(TransactionDB.user_id == user_id)

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
    user_id: int,
    filters: TransactionFilters,
    order_by: Literal["date", "value"] = "date",
    order_dir: Literal["asc", "desc"] = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[TransactionOut]:
    order_column = ORDER_COLUMNS[order_by]
    order_column = order_column.asc() if order_dir == "asc" else order_column.desc()

    query = db.query(TransactionDB, Categories.name).outerjoin(Categories, TransactionDB.category_id == Categories.id)
    rows = (
        _apply_filters(query, user_id, filters)
        .order_by(order_column, TransactionDB.id.desc())
        .limit(max(1, min(limit, MAX_LIST_LIMIT)))
        .offset(max(0, offset))
        .all()
    )

    return _to_out(rows)


def list_all_transactions(db: Session, user_id: int) -> list[TransactionOut]:
    """Every transaction of the user, newest first. No page limit: meant for exports."""
    query = db.query(TransactionDB, Categories.name).outerjoin(Categories, TransactionDB.category_id == Categories.id)
    rows = (
        query.filter(TransactionDB.user_id == user_id)
        .order_by(TransactionDB.transactioned_at.desc(), TransactionDB.id.desc())
        .all()
    )
    return _to_out(rows)


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
        )
        for t, category_name in rows
    ]


def aggregate_transactions(
    db: Session,
    user_id: int,
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
        row = _apply_filters(db.query(*metrics), user_id, filters).one()
        return [TransactionAggregate(**row._mapping)]

    if group_by == "category":
        keys = [TransactionDB.category_id.label("category_id"), Categories.name.label("category_name")]
        query = db.query(*keys, *metrics).outerjoin(Categories, TransactionDB.category_id == Categories.id)
        query = _apply_filters(query, user_id, filters).group_by(*keys).order_by(func.sum(TransactionDB.value).desc())
        return [TransactionAggregate(**row._mapping) for row in query.all()]

    if group_by == "weekday":
        key = extract("dow", TransactionDB.transactioned_at).label("weekday")
        query = _apply_filters(db.query(key, *metrics), user_id, filters).group_by(key).order_by(key)
        return [TransactionAggregate(**row._mapping) for row in query.all()]

    parts = [extract(p, TransactionDB.transactioned_at).label(p) for p in PERIOD_PARTS[group_by]]
    query = _apply_filters(db.query(*parts, *metrics), user_id, filters).group_by(*parts).order_by(*parts)

    results = []
    for row in query.all():
        data = dict(row._mapping)
        period_values = [int(data.pop(p)) for p in PERIOD_PARTS[group_by]]
        data["period"] = "-".join(f"{v:02d}" for v in period_values)
        results.append(TransactionAggregate(**data))
    return results


def delete_transaction(db: Session, id, user_id: int):
    transaction = db.query(TransactionDB).filter_by(id=id, user_id=user_id).first()
    if transaction:
        db.delete(transaction)
        db.commit()
        return True
    return False


def category_exists(db: Session, category_id: int) -> bool:
    return db.query(Categories.id).filter_by(id=category_id).first() is not None


def update_transaction(db: Session, id: int, user_id: int, changes: TransactionUpdate):
    """Update one of the user's transactions. Returns it, or None if it is missing or not theirs."""
    transaction = db.query(TransactionDB).filter_by(id=id, user_id=user_id).first()
    if transaction is None:
        return None
    transaction.label = changes.label
    transaction.value = changes.value
    transaction.category_id = changes.category_id
    if changes.type is not None:
        transaction.type = changes.type
    if changes.transactioned_at is not None:
        transaction.transactioned_at = changes.transactioned_at
    transaction.updated_at = datetime.now()
    db.commit()
    return transaction

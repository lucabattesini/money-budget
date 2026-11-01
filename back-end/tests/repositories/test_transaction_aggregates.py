from datetime import date, datetime

import pytest

from api.repositories.transactions_repo import aggregate_transactions
from schemas.tables_schemas import TransactionFilters


@pytest.fixture
def seeded(user, make_transaction, category_ids):
    c = category_ids
    make_transaction(user, c["Alimentação"], "a", 1000, datetime(2026, 3, 1, 9))    # Sunday
    make_transaction(user, c["Alimentação"], "b", 3000, datetime(2026, 3, 1, 20))   # Sunday
    make_transaction(user, c["Transporte"], "c", 500, datetime(2026, 3, 2, 8))      # Monday
    make_transaction(user, c["Aluguel"], "d", 150000, datetime(2026, 4, 10, 12))    # Friday
    make_transaction(user, c["Outros"], "e", 2000, datetime(2025, 12, 25, 12))      # Thursday


def agg(db, user, group_by=None, **filters):
    return aggregate_transactions(db, user.id, TransactionFilters(**filters), group_by)


def test_overall_totals(db, user, seeded):
    [row] = agg(db, user)

    assert (row.total, row.count, row.max) == (156500, 5, 150000)
    assert row.average == pytest.approx(31300)


def test_overall_totals_for_nobody_are_zero(db, user):
    [row] = agg(db, user)

    assert (row.total, row.count, row.average, row.max) == (0, 0, 0, 0)


def test_group_by_category_is_ordered_by_total_descending(db, user, seeded, category_ids):
    rows = agg(db, user, "category")

    assert [(r.category_name, r.total, r.count) for r in rows] == [
        ("Aluguel", 150000, 1),
        ("Alimentação", 4000, 2),
        ("Outros", 2000, 1),
        ("Transporte", 500, 1),
    ]
    assert rows[1].category_id == category_ids["Alimentação"]
    assert rows[1].average == pytest.approx(2000)
    assert rows[1].max == 3000


def test_group_by_month(db, user, seeded):
    rows = agg(db, user, "month")

    assert [(r.period, r.total) for r in rows] == [("2025-12", 2000), ("2026-03", 4500), ("2026-04", 150000)]


def test_group_by_year(db, user, seeded):
    rows = agg(db, user, "year")

    assert [(r.period, r.total) for r in rows] == [("2025", 2000), ("2026", 154500)]


def test_group_by_day(db, user, seeded):
    rows = agg(db, user, "day", start_date=date(2026, 3, 1), end_date=date(2026, 3, 31))

    assert [(r.period, r.total, r.count) for r in rows] == [("2026-03-01", 4000, 2), ("2026-03-02", 500, 1)]


def test_group_by_weekday_uses_sunday_as_zero(db, user, seeded):
    rows = agg(db, user, "weekday")

    assert [(r.weekday, r.total) for r in rows] == [(0, 4000), (1, 500), (4, 2000), (5, 150000)]


def test_filters_apply_to_aggregates(db, user, seeded, category_ids):
    [row] = agg(db, user, start_date=date(2026, 3, 1), end_date=date(2026, 3, 31), category_ids=[category_ids["Alimentação"]])

    assert (row.total, row.count) == (4000, 2)


def test_grouping_with_no_matching_rows_is_empty(db, user, seeded):
    assert agg(db, user, "month", start_date=date(2030, 1, 1)) == []


def test_aggregates_ignore_other_users(db, user, other_user, seeded, make_transaction, category_ids):
    make_transaction(other_user, category_ids["Alimentação"], "theirs", 999_999, datetime(2026, 3, 1, 9))

    [row] = agg(db, user)
    by_category = {r.category_name: r.total for r in agg(db, user, "category")}

    assert row.total == 156500
    assert by_category["Alimentação"] == 4000

"""Filtering, ordering and pagination of the transaction repository.

The data below is chosen around boundaries: the last second of a day, midnight
of the next day, Sundays (weekday 0), ties on value, and a label with a '%'.
2026-03-01 and 2026-03-15 are Sundays, 2026-04-10 is a Friday, 2025-12-25 a Thursday.
"""

from datetime import date, datetime

import pytest

from api.controllers.transactions_controller import get_transactions
from api.repositories.transactions_repo import list_transactions
from schemas.tables import TransactionDB
from schemas.tables_schemas import GetTransactionsParams, TransactionFilters


@pytest.fixture
def seeded(db, user, make_transaction, category_ids):
    c = category_ids
    rows = {
        "cafe": make_transaction(user, c["Restaurantes e Bares"], "Café com Leite", 500, datetime(2026, 3, 1, 9, 0, 0)),
        "jantar": make_transaction(user, c["Restaurantes e Bares"], "Jantar 100%", 4000, datetime(2026, 3, 1, 23, 59, 59)),
        "uber": make_transaction(user, c["Transporte público"], "Uber centro", 1500, datetime(2026, 3, 2, 0, 0, 0)),
        "mercado": make_transaction(user, c["Supermercado"], "Mercado", 20000, datetime(2026, 3, 15, 12, 0, 0)),
        "aluguel": make_transaction(user, c["Aluguel"], "Aluguel abril", 150000, datetime(2026, 4, 10, 12, 0, 0)),
        "presente": make_transaction(user, c["Sem categoria"], "Presente", 3000, datetime(2025, 12, 25, 12, 0, 0)),
    }
    return rows


def labels(rows):
    return {r.label for r in rows}


def run(db, user, order_by="date", order_dir="desc", limit=50, offset=0, **filters):
    return list_transactions(db, user.family_id, TransactionFilters(**filters), order_by, order_dir, limit, offset)


# --- dates -------------------------------------------------------------------


def test_end_date_includes_the_whole_last_day(db, user, seeded):
    rows = run(db, user, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))

    assert labels(rows) == {"Café com Leite", "Jantar 100%"}  # 23:59:59 in, midnight of 03-02 out


def test_start_date_includes_midnight(db, user, seeded):
    rows = run(db, user, start_date=date(2026, 3, 2), end_date=date(2026, 3, 2))

    assert labels(rows) == {"Uber centro"}


def test_date_range_spanning_months(db, user, seeded):
    rows = run(db, user, start_date=date(2026, 3, 15), end_date=date(2026, 4, 10))

    assert labels(rows) == {"Mercado", "Aluguel abril"}


# --- search ------------------------------------------------------------------


def test_search_is_case_insensitive(db, user, seeded):
    assert labels(run(db, user, search="CAFÉ COM")) == {"Café com Leite"}


def test_search_treats_percent_literally(db, user, seeded):
    # '%' must not act as a wildcard: only the label that really contains it matches
    assert labels(run(db, user, search="%")) == {"Jantar 100%"}


def test_search_treats_underscore_literally(db, user, seeded):
    assert run(db, user, search="_") == []


# --- values ------------------------------------------------------------------


def test_value_bounds_are_inclusive(db, user, seeded):
    rows = run(db, user, min_value=1500, max_value=4000)

    assert labels(rows) == {"Uber centro", "Jantar 100%", "Presente"}


# --- categories --------------------------------------------------------------


def test_filter_by_categories(db, user, seeded, category_ids):
    rows = run(db, user, category_ids=[category_ids["Restaurantes e Bares"], category_ids["Transporte público"]])

    assert labels(rows) == {"Café com Leite", "Jantar 100%", "Uber centro"}


def test_exclude_categories(db, user, seeded, category_ids):
    rows = run(db, user, exclude_category_ids=[category_ids["Aluguel"], category_ids["Sem categoria"]])

    assert labels(rows) == {"Café com Leite", "Jantar 100%", "Uber centro", "Mercado"}


def test_unknown_category_id_matches_nothing(db, user, seeded):
    assert run(db, user, category_ids=[-1]) == []


def test_rows_carry_their_category_name(db, user, seeded):
    by_label = {r.label: r.category_name for r in run(db, user)}

    assert by_label["Mercado"] == "Supermercado"
    assert by_label["Uber centro"] == "Transporte público"


def test_transaction_without_a_category_is_still_listed(db, user, make_transaction):
    row = TransactionDB(
        family_id=user.family_id,
        user_id=user.id,
        label="No category",
        value=100,
        transactioned_at=datetime(2026, 1, 1),
        category_id=None,
    )
    db.add(row)
    db.commit()

    rows = run(db, user)

    assert [(r.label, r.category_name) for r in rows] == [("No category", None)]


# --- weekdays (0 = Sunday) ---------------------------------------------------


@pytest.mark.parametrize(
    "weekdays, expected",
    [
        ([0], {"Café com Leite", "Jantar 100%", "Mercado"}),
        ([1], {"Uber centro"}),
        ([4], {"Presente"}),
        ([5], {"Aluguel abril"}),
        ([0, 5], {"Café com Leite", "Jantar 100%", "Mercado", "Aluguel abril"}),
        ([2, 3, 6], set()),
    ],
)
def test_weekday_filter(db, user, seeded, weekdays, expected):
    assert labels(run(db, user, weekdays=weekdays)) == expected


# --- ordering and pagination -------------------------------------------------


def test_default_order_is_newest_first(db, user, seeded):
    rows = run(db, user)

    assert [r.label for r in rows] == [
        "Aluguel abril",
        "Mercado",
        "Uber centro",
        "Jantar 100%",
        "Café com Leite",
        "Presente",
    ]


def test_order_by_value(db, user, seeded):
    assert [r.value for r in run(db, user, order_by="value", order_dir="asc")] == [500, 1500, 3000, 4000, 20000, 150000]
    assert [r.value for r in run(db, user, order_by="value", order_dir="desc")][0] == 150000


def test_ties_are_broken_by_newest_id_first(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    same_time = datetime(2026, 1, 1, 12)
    first = make_transaction(user, cat, "first", 100, same_time)
    second = make_transaction(user, cat, "second", 100, same_time)

    by_date = run(db, user)
    by_value = run(db, user, order_by="value")

    assert [r.id for r in by_date] == [second.id, first.id]
    assert [r.id for r in by_value] == [second.id, first.id]


def test_limit_and_offset(db, user, seeded):
    page1 = run(db, user, limit=2)
    page2 = run(db, user, limit=2, offset=2)

    assert len(page1) == len(page2) == 2
    assert labels(page1).isdisjoint(labels(page2))
    assert [r.label for r in page1 + page2] == ["Aluguel abril", "Mercado", "Uber centro", "Jantar 100%"]


def test_limit_has_a_floor_of_one(db, user, seeded):
    assert len(run(db, user, limit=0)) == 1


def test_limit_is_capped_at_200(db, user, category_ids):
    db.add_all(
        TransactionDB(
            family_id=user.family_id,
            user_id=user.id,
            label=f"t{i}",
            value=1,
            transactioned_at=datetime(2026, 1, 1),
            category_id=category_ids["Sem categoria"],
        )
        for i in range(205)
    )
    db.commit()

    assert len(run(db, user, limit=10_000)) == 200


def test_negative_offset_is_treated_as_zero(db, user, seeded):
    assert [r.label for r in run(db, user, offset=-5, limit=1)] == ["Aluguel abril"]


# --- scoping -----------------------------------------------------------------


def test_other_users_rows_are_never_returned(db, user, other_user, seeded, make_transaction, category_ids):
    make_transaction(other_user, category_ids["Sem categoria"], "Not yours", 1, datetime(2026, 3, 1, 10))

    assert "Not yours" not in labels(run(db, user))
    assert "Not yours" not in labels(run(db, user, search="Not yours"))


# --- day and month filters (TKT-26) ---


def test_day_filter_matches_only_the_given_date(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "march 5th", when=datetime(2026, 3, 5, 12))
    make_transaction(user, cat, "april 5th", when=datetime(2026, 4, 5, 12))

    rows = get_transactions(db, GetTransactionsParams(organized_by="day", date=datetime(2026, 3, 5)), user.family_id)

    assert [r.label for r in rows] == ["march 5th"]


def test_month_filter_matches_only_the_given_year_and_month(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "march 2026", when=datetime(2026, 3, 5, 12))
    make_transaction(user, cat, "march 2025", when=datetime(2025, 3, 5, 12))

    rows = get_transactions(db, GetTransactionsParams(organized_by="month", date=datetime(2026, 3, 1)), user.family_id)

    assert [r.label for r in rows] == ["march 2026"]


def test_year_filter_still_matches_the_whole_year(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "dec 2025", when=datetime(2025, 12, 31, 23, 59, 59))
    make_transaction(user, cat, "jan 2026", when=datetime(2026, 1, 1, 0, 0, 0))
    make_transaction(user, cat, "dec 2026", when=datetime(2026, 12, 31, 23, 59, 59))
    make_transaction(user, cat, "jan 2027", when=datetime(2027, 1, 1, 0, 0, 0))

    rows = get_transactions(db, GetTransactionsParams(organized_by="year", date=datetime(2026, 6, 1)), user.family_id)

    assert sorted(r.label for r in rows) == ["dec 2026", "jan 2026"]


def test_december_month_filter_does_not_leak_into_january(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "dec", when=datetime(2026, 12, 31, 23, 59, 59))
    make_transaction(user, cat, "jan", when=datetime(2027, 1, 1, 0, 0, 0))

    rows = get_transactions(
        db, GetTransactionsParams(organized_by="month", date=datetime(2026, 12, 15)), user.family_id
    )

    assert [r.label for r in rows] == ["dec"]


def test_day_filter_includes_the_whole_day_and_nothing_of_the_next(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "midnight", when=datetime(2026, 3, 5, 0, 0, 0))
    make_transaction(user, cat, "last second", when=datetime(2026, 3, 5, 23, 59, 59))
    make_transaction(user, cat, "next day", when=datetime(2026, 3, 6, 0, 0, 0))

    rows = get_transactions(
        db, GetTransactionsParams(organized_by="day", date=datetime(2026, 3, 5, 15)), user.family_id
    )

    assert sorted(r.label for r in rows) == ["last second", "midnight"]


def test_no_grouping_returns_everything(db, user, make_transaction, category_ids):
    cat = category_ids["Sem categoria"]
    make_transaction(user, cat, "a", when=datetime(2025, 1, 1))
    make_transaction(user, cat, "b", when=datetime(2026, 3, 5))

    assert len(get_transactions(db, GetTransactionsParams(), user.family_id)) == 2


@pytest.mark.parametrize("organized_by", ["year", "month", "day"])
def test_the_last_year_the_calendar_has_does_not_crash_the_filter(
    db, user, make_transaction, category_ids, organized_by
):
    make_transaction(user, category_ids["Sem categoria"], "recent", when=datetime(2026, 3, 5, 12))

    rows = get_transactions(
        db, GetTransactionsParams(organized_by=organized_by, date=datetime(9999, 12, 31)), user.family_id
    )

    assert rows == []

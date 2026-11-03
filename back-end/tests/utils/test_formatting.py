from datetime import date, datetime
from decimal import Decimal

import pytest

from api.utils.formatting import (
    format_amount_br,
    format_date_br,
    neutralize_formula,
    parse_amount,
    parse_date_br,
    parse_type,
    remove_formula_guard,
    type_label,
)


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("25.5"), "25,50"),
        (Decimal("0.05"), "0,05"),
        (Decimal("0"), "0,00"),
        (Decimal("1234.56"), "1.234,56"),
        (Decimal("1000000"), "1.000.000,00"),
        (Decimal("19.999"), "20,00"),  # always two decimals
        (2550, "2.550,00"),  # plain integers are reais, not cents
    ],
)
def test_amounts_have_two_decimals_a_comma_and_dots_between_thousands(amount, text):
    assert format_amount_br(amount) == text


def test_dates_are_day_month_year_for_dates_and_datetimes():
    assert format_date_br(date(2026, 3, 5)) == "05/03/2026"
    assert format_date_br(datetime(2026, 12, 31, 23, 59)) == "31/12/2026"
    assert format_date_br(None) == ""


def test_type_labels():
    assert type_label("debit") == "Débito"
    assert type_label("credit") == "Crédito"
    assert type_label(None) == "Débito"


@pytest.mark.parametrize("text", ["=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"])
def test_text_that_looks_like_a_formula_is_neutralized(text):
    assert neutralize_formula(text) == "'" + text


@pytest.mark.parametrize("text", ["Almoço", "", "a=b", "1+1", " =x", "'já tem"])
def test_ordinary_text_is_left_alone(text):
    assert neutralize_formula(text) == text


@pytest.mark.parametrize(
    ("amount", "currency", "language", "text"),
    [
        (1234.5, "BRL", "pt", "R$ 1.234,50"),
        (1234.5, "BRL", "en", "R$1,234.50"),
        (1234.5, "USD", "en", "US$1,234.50"),
        (1234.5, "USD", "pt", "US$ 1.234,50"),
        (1234.5, "CAD", "en", "CA$1,234.50"),
        (7, "EUR", "pt", "€ 7,00"),
        (0.05, "GBP", "en", "£0.05"),
        (1000000, "BRL", "pt", "R$ 1.000.000,00"),
    ],
)
def test_money_follows_the_currency_for_the_symbol_and_the_language_for_the_separators(
    amount, currency, language, text
):
    from api.utils.formatting import format_money

    assert format_money(amount, currency, language) == text


def test_the_day_and_month_follow_the_language():
    from api.utils.formatting import format_day_month

    assert format_day_month(date(2026, 3, 5), "pt") == "05/03"
    assert format_day_month(date(2026, 3, 5), "en") == "03/05"


# --- reading what the export writes ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1.234,56", Decimal("1234.56")),
        ("12,5", Decimal("12.5")),
        ("12,50", Decimal("12.50")),
        ("12.50", Decimal("12.50")),
        ("1234", Decimal("1234")),
        ("1.234", Decimal("1234")),  # dots grouped in threes are thousands
        ("1.234.567,89", Decimal("1234567.89")),
        ("R$ 1.234,56", Decimal("1234.56")),
        ("-5,00", Decimal("-5.00")),
        (" 7 ", Decimal("7")),
    ],
)
def test_parse_amount_reads_brazilian_and_plain_numbers(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1,234,56", "12,345", "1e5", "NaN", "Infinity", "1 2 a", "--3", "1,"])
def test_parse_amount_rejects_what_is_not_an_amount(text):
    assert parse_amount(text) is None


def test_parse_amount_undoes_format_amount_br():
    for amount in (Decimal("0.05"), Decimal("1234.5"), Decimal("1000000")):
        assert parse_amount(format_amount_br(amount)) == amount


def test_parse_date_br_reads_only_real_days_in_that_format():
    assert parse_date_br("15/03/2026") == date(2026, 3, 15)
    assert parse_date_br(" 01/12/2025 ") == date(2025, 12, 1)
    for bad in ["2026-03-15", "15/3/2026", "31/02/2026", "15/13/2026", "", "ontem"]:
        assert parse_date_br(bad) is None


def test_parse_type_accepts_the_labels_and_defaults_to_debit():
    assert parse_type("Débito") == "debit"
    assert parse_type("crédito") == "credit"
    assert parse_type("CREDITO") == "credit"
    assert parse_type("") == "debit"
    assert parse_type(None) == "debit"
    assert parse_type("Pix") is None


@pytest.mark.parametrize("text", ["=1+1", "+55", "-5", "@user"])
def test_the_formula_guard_is_removed_again(text):
    assert remove_formula_guard(neutralize_formula(text)) == text


def test_an_apostrophe_in_front_of_ordinary_text_stays():
    assert remove_formula_guard("'Almoço") == "'Almoço"
    assert remove_formula_guard("Almoço") == "Almoço"

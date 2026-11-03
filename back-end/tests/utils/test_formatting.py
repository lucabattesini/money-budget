from datetime import date, datetime
from decimal import Decimal

import pytest

from api.utils.formatting import (
    format_amount_br,
    format_date_br,
    neutralize_formula,
    parse_amount,
    parse_date,
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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1,234.56", Decimal("1234.56")),
        ("1,234,567.89", Decimal("1234567.89")),
        ("1,234", Decimal("1234")),  # three digits after the mark: a group, decimals have at most two
        ("1,234,567", Decimal("1234567")),
        ("12.5", Decimal("12.5")),
        ("0.05", Decimal("0.05")),
        ("$1,234.56", Decimal("1234.56")),
        ("US$ 1,234.56", Decimal("1234.56")),
        ("-1,234.56", Decimal("-1234.56")),
        ("12,345", Decimal("12345")),
    ],
)
def test_parse_amount_reads_american_numbers_too(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["1,5.5", "1.2.3", "1.234,56,7", "1,234.567", "12,3456", ".5"])
def test_parse_amount_rejects_marks_in_the_wrong_places(text):
    assert parse_amount(text) is None


@pytest.mark.parametrize("text", ["", "abc", "1,234,56", "1e5", "NaN", "Infinity", "1 2 a", "--3", "1,"])
def test_parse_amount_rejects_what_is_not_an_amount(text):
    assert parse_amount(text) is None


def test_parse_amount_undoes_format_amount_br():
    for amount in (Decimal("0.05"), Decimal("1234.5"), Decimal("1000000")):
        assert parse_amount(format_amount_br(amount)) == amount


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


# --- dates in either order ---------------------------------------------------------------------------------------------


def test_parse_date_reads_the_day_first_by_default():
    assert parse_date("15/03/2026") == date(2026, 3, 15)
    assert parse_date("05/03/2026") == date(2026, 3, 5)  # the 5th of March, not the 3rd of May


def test_parse_date_reads_the_month_first_when_asked():
    assert parse_date("03/15/2026", "month_first") == date(2026, 3, 15)
    assert parse_date("05/03/2026", "month_first") == date(2026, 5, 3)  # the same text, the other way round


@pytest.mark.parametrize("order", ["day_first", "month_first", "iso"])
def test_the_iso_date_is_accepted_in_every_order_unless_strict(order):
    assert parse_date("2026-10-13", order) == date(2026, 10, 13)
    assert parse_date("2026-03-05", order) == date(2026, 3, 5)


def test_the_iso_format_reads_year_month_day_only():
    assert parse_date("2026-10-13", "iso", strict=True) == date(2026, 10, 13)
    assert parse_date("2026-1-3", "iso", strict=True) == date(2026, 1, 3)
    for other in ["13/10/2026", "10/13/2026", "13-10-2026", "2026/10/13"]:
        assert parse_date(other, "iso", strict=True) is None, other


@pytest.mark.parametrize("order", ["day_first", "month_first"])
def test_a_strict_slashed_format_refuses_the_iso_date(order):
    assert parse_date("2026-10-13", order, strict=True) is None
    assert parse_date("2026-10-13", order, strict=False) == date(2026, 10, 13)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("15-03-2026", date(2026, 3, 15)),
        ("15.03.2026", date(2026, 3, 15)),
        ("5/3/2026", date(2026, 3, 5)),
        (" 15/03/2026 ", date(2026, 3, 15)),
    ],
)
def test_parse_date_accepts_other_separators_and_short_numbers(text, expected):
    assert parse_date(text) == expected


def test_parse_date_rejects_days_that_do_not_exist_in_that_order():
    assert parse_date("03/15/2026") is None  # there is no month 15
    assert parse_date("15/03/2026", "month_first") is None
    for bad in ["31/02/2026", "00/03/2026", "15/03/26", "2026-13-01", "2026-02-30", "15/03", "ontem", ""]:
        assert parse_date(bad) is None, bad


# --- an amount in one chosen style ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "style, text, expected",
    [
        ("br", "1.234,56", Decimal("1234.56")),
        ("br", "1.234", Decimal("1234")),
        ("br", "12,5", Decimal("12.5")),
        ("br", "1234", Decimal("1234")),
        ("br", "R$ -1.234,56", Decimal("-1234.56")),
        ("us", "1,234.56", Decimal("1234.56")),
        ("us", "1,234", Decimal("1234")),
        ("us", "12.5", Decimal("12.5")),
        ("us", "$1,234.56", Decimal("1234.56")),
        ("us", "-1,234.56", Decimal("-1234.56")),
    ],
)
def test_an_amount_is_read_in_the_style_that_was_chosen(style, text, expected):
    assert parse_amount(text, style) == expected


@pytest.mark.parametrize(
    "style, text",
    [
        ("br", "1,234.56"),  # the American way is not accepted when Brazilian was chosen
        ("br", "1,234"),  # three decimals
        ("br", "12.5"),  # a dot groups thousands, so it needs three digits after it
        ("us", "1.234,56"),
        ("us", "1.234"),  # in the American style a dot is the decimal mark: three decimals
        ("us", "12,5"),
        ("br", "1.234,5,6"),
        ("us", "1,234.5.6"),
        ("br", "12.34.567,89"),
    ],
)
def test_an_amount_in_the_other_style_is_refused_when_one_was_chosen(style, text):
    assert parse_amount(text, style) is None


def test_the_same_text_means_different_amounts_in_the_two_styles():
    assert parse_amount("1.234", "br") == Decimal("1234")
    assert parse_amount("1,234", "br") is None
    assert parse_amount("1,234", "us") == Decimal("1234")
    assert parse_amount("1.234", "us") is None

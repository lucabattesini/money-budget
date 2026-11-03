from datetime import date, datetime
from decimal import Decimal

import pytest

from api.utils.formatting import format_amount_br, format_date_br, neutralize_formula, type_label


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

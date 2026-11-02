"""Formatting of values for people (Brazilian conventions). Pure functions, no I/O."""

from datetime import date, datetime
from decimal import Decimal

TYPE_LABELS = {"debit": "Débito", "credit": "Crédito"}

# A spreadsheet treats a cell that starts with one of these as a formula
_FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")


def format_amount_br(amount: Decimal | int) -> str:
    """1234.5 -> "1.234,50": dot between thousands, comma before exactly two decimals."""
    return f"{Decimal(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date_br(value: date | datetime | None) -> str:
    """The day as DD/MM/YYYY; empty for a missing date."""
    return "" if value is None else value.strftime("%d/%m/%Y")


def type_label(transaction_type: str | None) -> str:
    """ "debit" -> "Débito", "credit" -> "Crédito". A missing type is a debit, like in the database."""
    return TYPE_LABELS[transaction_type or "debit"]


def neutralize_formula(text: str) -> str:
    """Stop text typed by a user from being run as a formula when the file is opened in Excel.

    Text starting with = + - @ gets a leading apostrophe, the usual defence against CSV injection.
    """
    return "'" + text if text.startswith(_FORMULA_STARTERS) else text

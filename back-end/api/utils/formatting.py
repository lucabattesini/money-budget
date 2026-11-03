"""Formatting of values for people (Brazilian conventions, except where a family's language is given). Pure functions,
no I/O."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from schemas.family_settings import CURRENCY_SYMBOLS

TYPE_LABELS = {"debit": "Débito", "credit": "Crédito"}

# A spreadsheet treats a cell that starts with one of these as a formula
_FORMULA_STARTERS = ("=", "+", "-", "@", "\t", "\r")


def format_amount_br(amount: Decimal | int) -> str:
    """1234.5 -> "1.234,50": dot between thousands, comma before exactly two decimals."""
    return f"{Decimal(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_money(amount: Decimal | float | int, currency: str = "BRL", language: str = "pt") -> str:
    """An amount the way a family sees it: Portuguese "R$ 1.234,50", English "R$1,234.50" (the symbol follows the
    currency, the separators follow the language)."""
    number = f"{Decimal(str(amount)):,.2f}"
    symbol = CURRENCY_SYMBOLS[currency]
    if language == "en":
        return f"{symbol}{number}"
    return f"{symbol} " + number.replace(",", "X").replace(".", ",").replace("X", ".")


def format_day_month(value: date | datetime, language: str = "pt") -> str:
    """The day without the year: Portuguese "05/03", English "03/05"."""
    return value.strftime("%m/%d" if language == "en" else "%d/%m")


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


# --- The reverse: reading what people (and our own export) wrote -----------------------------------------------------

_THOUSANDS_ONLY = re.compile(r"\d{1,3}(\.\d{3})+")


def parse_amount(text: str) -> Decimal | None:
    """ "1.234,56" -> Decimal("1234.56"). Also "12,5", "12.50", "1234" and "R$ 1.234,56". None if it is not an amount.

    A comma is the decimal mark and dots in front of it are thousands. Without a comma, dots grouped in threes
    ("1.234.567") are thousands and any other dot ("12.50") is a decimal point. At most two decimal places: an amount
    in cents cannot hold more. A minus sign is kept, so the caller can say "must be greater than zero".
    """
    cleaned = text.replace("R$", "").replace("\xa0", " ").strip().replace(" ", "")
    if not cleaned:
        return None
    sign = ""
    if cleaned[0] in "+-":
        sign, cleaned = cleaned[0], cleaned[1:]
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif _THOUSANDS_ONLY.fullmatch(cleaned):
        cleaned = cleaned.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", cleaned):
        return None
    try:
        return Decimal(sign + cleaned)
    except InvalidOperation:  # pragma: no cover - the pattern above already rules this out
        return None


def parse_date_br(text: str) -> date | None:
    """ "15/03/2026" -> date(2026, 3, 15). None if it is not a real day in exactly that format."""
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", text.strip()):
        return None
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_type(text: str | None) -> str | None:
    """ "Débito" -> "debit", "Crédito" -> "credit" (any case, with or without the accent). An empty cell is a debit.
    None if it is anything else."""
    wanted = (text or "").strip().casefold()
    if not wanted:
        return "debit"
    for key, label in TYPE_LABELS.items():
        if wanted in (label.casefold(), key):
            return key
    return {"debito": "debit", "credito": "credit"}.get(wanted)


def remove_formula_guard(text: str) -> str:
    """Undo neutralize_formula: "'=SOMA(A1)" -> "=SOMA(A1)". An apostrophe in front of anything else stays."""
    return text[1:] if text.startswith("'") and text[1:].startswith(_FORMULA_STARTERS) else text

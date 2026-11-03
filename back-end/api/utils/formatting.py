"""Formatting of values for people (Brazilian conventions, except where a family's language is given). Pure functions,
no I/O."""

import re
from datetime import date, datetime
from decimal import Decimal

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

_CURRENCY_SYMBOLS = re.compile(r"(?i)us\$|r\$|[$€£]")


def _grouped(text: str, mark: str) -> bool:
    """True if `text` is digits grouped in threes by `mark`: "1.234.567" (the first group has one to three digits)."""
    return re.fullmatch(rf"\d{{1,3}}(?:{re.escape(mark)}\d{{3}})+", text) is not None


AMOUNT_STYLES = ("auto", "br", "us")  # br: 1.234,56  us: 1,234.56


def parse_amount(text: str, style: str = "auto") -> Decimal | None:
    """The amount in a cell, written the Brazilian way ("1.234,56") or the American way ("1,234.56").

    With `style` "br" or "us" only that way is accepted, strictly: "br" reads "1.234" as 1234 and refuses "1,234"
    (three decimals); "us" is the other way round. With "auto" either is, as described below.

    "R$ 1.234,56", "$1,234.56", "12,5", "12.50", "1234" and "-5,00" work too. None if it is not an amount.
    With both marks, the last one is the decimal mark and the other groups thousands. With one kind of mark: when it
    appears more than once, or when exactly three digits follow it, it groups thousands ("1.234", "1,234", "1.234.567");
    otherwise it is the decimal mark ("12,5", "12.50"). Decimals are at most two, because an amount in cents cannot
    hold more, so three digits after a mark can only be a group. A minus sign is kept, so the caller can say "negative is
    not allowed here".
    """
    cleaned = _CURRENCY_SYMBOLS.sub("", text).replace("\xa0", " ").strip().replace(" ", "")
    sign = ""
    if cleaned[:1] in ("+", "-"):
        sign, cleaned = cleaned[0], cleaned[1:]
    if not cleaned or not re.fullmatch(r"[\d.,]+", cleaned):
        return None

    if style in ("br", "us"):
        decimal_mark, thousands_mark = (",", ".") if style == "br" else (".", ",")
        whole, has_fraction, fraction = cleaned.partition(decimal_mark)
        if not (whole.isdigit() or _grouped(whole, thousands_mark)):
            return None
        if has_fraction and not re.fullmatch(r"\d{1,2}", fraction):
            return None
        return Decimal(sign + whole.replace(thousands_mark, "") + ("." + fraction if has_fraction else ""))

    if "," in cleaned and "." in cleaned:
        decimal_mark = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_mark = "." if decimal_mark == "," else ","
        whole, _, fraction = cleaned.rpartition(decimal_mark)
        if thousands_mark in fraction or not (_grouped(whole, thousands_mark) or whole.isdigit()):
            return None
        cleaned = whole.replace(thousands_mark, "") + "." + fraction
    else:
        mark = "," if "," in cleaned else "." if "." in cleaned else ""
        if mark:
            if cleaned.count(mark) > 1 or _grouped(cleaned, mark):
                if not _grouped(cleaned, mark):
                    return None
                cleaned = cleaned.replace(mark, "")
            else:
                cleaned = cleaned.replace(mark, ".")

    if not re.fullmatch(r"\d+(\.\d{1,2})?", cleaned):
        return None
    return Decimal(sign + cleaned)


_SLASHED_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
_ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def date_parts(text: str) -> tuple[int, int, int] | None:
    """(first number, second number, year) of a date written "15/03/2026", "03-15-2026" or "15.03.2026"; None for any
    other text. Which of the two is the day and which the month is not known from the text alone."""
    match = _SLASHED_DATE.fullmatch(text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


DATE_FORMATS = ("day_first", "month_first", "iso")  # 15/03/2026, 03/15/2026, 2026-03-15


def parse_date(text: str, order: str = "day_first", strict: bool = False) -> date | None:
    """A day written in one of the three ways in DATE_FORMATS: "15/03/2026" (day first, the Brazilian way),
    "03/15/2026" (month first, the American way) or "2026-03-15" (year first, the same everywhere). The numbers may be
    separated by "/", "-" or "." and may have one digit.

    `order` is how a slashed date is read. Unless `strict`, "2026-03-15" is accepted whatever the order is; when
    strict, only the chosen way is. "iso" means only year first. None if it is not a real day.
    """
    text = text.strip()
    try:
        if order == "iso" or not strict:
            iso = _ISO_DATE.fullmatch(text)
            if iso:
                return date(int(iso[1]), int(iso[2]), int(iso[3]))
        if order == "iso":
            return None
        parts = date_parts(text)
        if parts is None:
            return None
        first, second, year = parts
        return date(year, first, second) if order == "month_first" else date(year, second, first)
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

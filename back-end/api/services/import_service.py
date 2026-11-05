"""Checks a table read from a spreadsheet and turns it into transactions-to-be.

The fields are the columns the export writes (see export_service.py), so an exported file can be imported back and its
columns are matched by themselves. A file whose columns are named differently is matched by the person. The whole table
is checked and every problem is collected, so the person can fix the file once instead of once per error.
"""

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from api.gateways.documents import Cell
from api.utils.formatting import (
    date_parts,
    parse_amount,
    parse_date,
    parse_type,
    remove_formula_guard,
)

REQUIRED_FIELDS = ["Data", "Descrição", "Categoria", "Valor"]
OPTIONAL_FIELDS = ["Tipo", "Pessoa"]
FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
MAX_LABEL = 100  # the size of the column
MAX_CENTS = 2147483647  # must fit the 32-bit column
FIRST_YEAR = 1900
DAY_FIRST = "day_first"  # 15/03/2026 is the 15th of March
MONTH_FIRST = "month_first"  # 03/15/2026 is the 15th of March
ISO = "iso"  # 2026-03-15
DATE_ORDERS = ("auto", DAY_FIRST, MONTH_FIRST, ISO)
# How the sign of the amount is read
TYPE_COLUMN = "type_column"  # the amount is always positive; the Tipo column says which way the money went
NEGATIVE_DEBIT = "negative_debit"  # a negative amount is money going out, a positive one money coming in
NEGATIVE_CREDIT = "negative_credit"  # the other way round
SIGNS = (TYPE_COLUMN, NEGATIVE_DEBIT, NEGATIVE_CREDIT)


@dataclass(frozen=True)
class Problem:
    row: int  # the row number in the file, as the spreadsheet shows it (the header is row 1)
    message: str


def simple_name(name: str) -> str:
    """A column name as it is compared: no case, no accents, no spaces around it."""
    decomposed = unicodedata.normalize("NFKD", name.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def suggest_mapping(columns: list[str]) -> dict[str, int | None]:
    """The position of the file column named like each field (ignoring case and accents), or None. A column is
    suggested for one field only."""
    taken: set[int] = set()
    suggested: dict[str, int | None] = {}
    for field in FIELDS:
        position = next(
            (i for i, name in enumerate(columns) if i not in taken and simple_name(name) == simple_name(field)), None
        )
        suggested[field] = position
        if position is not None:
            taken.add(position)
    return suggested


def mapping_problem(mapping: dict[str, int | None], column_count: int) -> str | None:
    """What is wrong with the person's matching of columns, or None if it can be used."""
    unknown = [field for field in mapping if field not in FIELDS]
    if unknown:
        return f"Campo desconhecido: {unknown[0]}."
    missing = [field for field in REQUIRED_FIELDS if mapping.get(field) is None]
    if missing:
        return "Escolha a coluna de: " + ", ".join(missing) + "."
    chosen = [position for position in mapping.values() if position is not None]
    if any(position < 0 or position >= column_count for position in chosen):
        return "Essa coluna não existe no arquivo."
    if len(chosen) != len(set(chosen)):
        return "Uma mesma coluna não pode ser usada para dois campos."
    return None


# A cell in the database (JSON): text stays text; a number or a date needs a tag to come back as what it was.
def encode_cell(cell: Cell):
    if isinstance(cell, Decimal):
        return {"n": str(cell)}
    if isinstance(cell, date):
        return {"d": cell.isoformat()}
    if cell is None or isinstance(cell, str):
        return cell
    return str(cell)  # nothing else can be kept in the database as it is


def decode_cell(value) -> Cell:
    if isinstance(value, dict):
        return Decimal(value["n"]) if "n" in value else date.fromisoformat(value["d"])
    return value


def display_cell(value) -> str:
    """A stored cell as the person would see it in the spreadsheet, to recognise the columns by."""
    cell = decode_cell(value)
    if cell is None:
        return ""
    if isinstance(cell, Decimal):
        return format(cell.normalize(), "f")
    if isinstance(cell, date):
        return cell.strftime("%d/%m/%Y")
    return str(cell)


def _text(cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, Decimal):  # a description or category that is only digits
        return format(cell.normalize(), "f")
    if isinstance(cell, date):
        return cell.strftime("%d/%m/%Y")
    return remove_formula_guard(str(cell)).strip()


def resolve_date_order(raw_rows: list[list], date_position: int, requested: str) -> str:
    """Whether the dates written as text are day first or month first.

    `requested` is what the person chose; "auto" looks at the file: a first number above 12 (15/03/2026) can only be a
    day, a second number above 12 (03/15/2026) can only be a day too, so the order is known as soon as one date shows
    it. If no date does, or they contradict each other, it is day first: the order of the file the app itself exports
    (and of the page that describes the format). The person is told how the dates were read and can choose.
    Real date cells are the same in every order, and "2026-03-15" too unless the person chose a strict format.
    """
    if requested in (DAY_FIRST, MONTH_FIRST, ISO):
        return requested
    day_first = month_first = False
    for stored in raw_rows:
        cell = decode_cell(stored[date_position]) if date_position < len(stored) else None
        parts = date_parts(cell) if isinstance(cell, str) else None
        if parts:
            day_first = day_first or parts[0] > 12
            month_first = month_first or parts[1] > 12
    if day_first != month_first:
        return DAY_FIRST if day_first else MONTH_FIRST
    return DAY_FIRST


def _read_date(cell, today: date, order: str, strict: bool) -> tuple[date | None, str | None]:
    if cell is None:
        return None, "a data é obrigatória."
    parsed = cell if isinstance(cell, date) else parse_date(cell, order, strict) if isinstance(cell, str) else None
    if parsed is None or parsed.year < FIRST_YEAR:
        return None, "a data não é válida (use por exemplo 15/03/2026, 03/15/2026 ou 2026-03-15, como escolhido)."
    if parsed > today:
        return None, "a data não pode ser no futuro."
    return parsed, None


def _read_amount(cell, style: str) -> tuple[int | None, str | None]:
    """The amount in cents, with its sign. Whether it is allowed to be negative is for the caller to say."""
    if cell is None:
        return None, "o valor é obrigatório."
    amount = cell if isinstance(cell, Decimal) else parse_amount(cell, style) if isinstance(cell, str) else None
    if amount is None:
        return None, "o valor não é um número (use por exemplo 1.234,56 ou 1,234.56, como escolhido)."
    cents = amount * 100
    if cents != cents.to_integral_value():
        return None, "o valor pode ter no máximo duas casas decimais."
    if abs(cents) > MAX_CENTS:
        return None, "o valor é grande demais."
    return int(cents), None


def suggest_sign(raw_rows: list[list], mapping: dict[str, int | None]) -> str:
    """NEGATIVE_DEBIT when the file has no column for the type but has negative amounts (a bank statement): the sign
    is then the only way to tell. Otherwise TYPE_COLUMN."""
    position = mapping.get("Valor")
    if mapping.get("Tipo") is not None or position is None:
        return TYPE_COLUMN
    for stored in raw_rows:
        cell = decode_cell(stored[position]) if position < len(stored) else None
        if (isinstance(cell, Decimal) and cell < 0) or (isinstance(cell, str) and cell.strip().startswith("-")):
            return NEGATIVE_DEBIT
    return TYPE_COLUMN


def check_table(
    raw_rows: list[list],
    mapping: dict[str, int | None],
    today: date,
    date_order: str = DAY_FIRST,
    amount_style: str = "auto",
    sign: str = TYPE_COLUMN,
    strict_dates: bool = False,
    members: dict[str, int | None] | None = None,
) -> tuple[list[dict], list[Problem]]:
    """The valid rows (as plain dicts, ready to be kept) and every problem found.

    `raw_rows` are the stored cells (see encode_cell) and `mapping` says which position holds each field and `date_order` (DAY_FIRST, MONTH_FIRST or ISO, see
    resolve_date_order) how dates written as text are read (`strict_dates`: only that way, which is what the person
    gets when they choose a format instead of leaving it on automatic),
    `amount_style` ("auto", "br" or "us") how amounts are written and `sign` how the sign of the amount is read
    (TYPE_COLUMN: always positive, Tipo says the direction; otherwise the sign says it and Tipo is not used).
    `members` maps the name of each person of the family (see simple_name) to their id, or to None when two people have
    that name: the Pessoa column is read with it, and an empty cell means the person importing.
    Rows that are empty all over are skipped. A category is only checked to be filled in; whether it exists is settled
    in a later step.
    """
    rows: list[dict] = []
    problems: list[Problem] = []

    for position, stored in enumerate(raw_rows):
        number = position + 2  # the header is row 1
        cells = [decode_cell(value) for value in stored]
        if not any(cell is not None for cell in cells):
            continue

        def cell(name: str):
            index = mapping.get(name)
            return cells[index] if index is not None and index < len(cells) else None

        found: list[str] = []
        day, error = _read_date(cell("Data"), today, date_order, strict_dates)
        if error:
            found.append(error)

        label = _text(cell("Descrição"))
        if not label:
            found.append("a descrição é obrigatória.")
        elif len(label) > MAX_LABEL:
            found.append(f"a descrição tem {len(label)} caracteres e o máximo é {MAX_LABEL}.")

        category = _text(cell("Categoria"))
        if not category:
            found.append("a categoria é obrigatória.")
        if "\x00" in label or "\x00" in category:  # the database cannot hold it
            found.append("a descrição ou a categoria tem um caractere inválido.")

        cents, error = _read_amount(cell("Valor"), amount_style)
        kind = "debit"
        if error:
            found.append(error)
        elif sign == TYPE_COLUMN:
            if cents < 0:
                found.append(
                    "o valor não pode ser negativo (escolha o sinal do valor se o arquivo usa negativo para débito)."
                )
            kind = parse_type(_text(cell("Tipo")))
            if kind is None:
                found.append("o tipo precisa ser Débito ou Crédito.")
        elif cents != 0:  # a zero has no direction: it stays a debit, the default
            out_is_negative = sign == NEGATIVE_DEBIT
            kind = "debit" if (cents < 0) == out_is_negative else "credit"
            cents = abs(cents)

        person = _text(cell("Pessoa"))
        person_id = None
        if person:
            if simple_name(person) not in (members or {}):
                found.append(f'a pessoa "{person}" não é da família.')
            elif (person_id := members[simple_name(person)]) is None:
                found.append(f'há mais de uma pessoa chamada "{person}" na família.')

        if found:
            problems.extend(Problem(number, message[0].upper() + message[1:]) for message in found)
        else:
            rows.append(
                {
                    "row": number,
                    "date": day.isoformat(),
                    "label": label,
                    "value": cents,
                    "type": kind,
                    "category": category,
                    "user_id": person_id,  # None: the person importing
                }
            )
    return rows, problems

"""Checks a table read from a spreadsheet and turns it into transactions-to-be.

The columns are the ones the export writes (see export_service.py), so an exported file can be imported back. The whole
table is checked and every problem is collected, so the person can fix the file once instead of once per error.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from api.gateways.documents import Table
from api.utils.formatting import parse_amount, parse_date_br, parse_type, remove_formula_guard

REQUIRED_COLUMNS = ["Data", "Descrição", "Categoria", "Valor"]
OPTIONAL_COLUMNS = ["Tipo"]
MAX_LABEL = 100  # the size of the column
MAX_CENTS = 2147483647  # must fit the 32-bit column
FIRST_YEAR = 1900


class MissingColumns(ValueError):
    """The first row does not have the columns the import needs. The message is for the person."""


@dataclass(frozen=True)
class Problem:
    row: int  # the row number in the file, as the spreadsheet shows it (the header is row 1)
    message: str


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _find_columns(table: Table) -> dict[str, int]:
    """Where each wanted column is (by name, ignoring case and spaces around it; extra columns are ignored)."""
    found: dict[str, int] = {}
    for wanted in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        for index, name in enumerate(table.columns):
            if _same(name, wanted):
                found[wanted] = index
                break
    missing = [name for name in REQUIRED_COLUMNS if name not in found]
    if missing:
        raise MissingColumns("Faltam colunas na primeira linha: " + ", ".join(missing) + ".")
    return found


def _text(cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, Decimal):  # a description or category that is only digits
        return format(cell.normalize(), "f")
    if isinstance(cell, date):
        return cell.strftime("%d/%m/%Y")
    return remove_formula_guard(str(cell)).strip()


def _read_date(cell, today: date) -> tuple[date | None, str | None]:
    if cell is None:
        return None, "a data é obrigatória."
    parsed = cell if isinstance(cell, date) else parse_date_br(cell) if isinstance(cell, str) else None
    if parsed is None or parsed.year < FIRST_YEAR:
        return None, "a data não é válida (use DD/MM/AAAA, por exemplo 15/03/2026)."
    if parsed > today:
        return None, "a data não pode ser no futuro."
    return parsed, None


def _read_amount(cell) -> tuple[int | None, str | None]:
    if cell is None:
        return None, "o valor é obrigatório."
    amount = cell if isinstance(cell, Decimal) else parse_amount(cell) if isinstance(cell, str) else None
    if amount is None:
        return None, "o valor não é um número (use por exemplo 1.234,56)."
    if amount <= 0:
        return None, "o valor precisa ser maior que zero."
    cents = amount * 100
    if cents != cents.to_integral_value():
        return None, "o valor pode ter no máximo duas casas decimais."
    if cents > MAX_CENTS:
        return None, "o valor é grande demais."
    return int(cents), None


def check_table(table: Table, today: date) -> tuple[list[dict], list[Problem]]:
    """The valid rows (as plain dicts, ready to be kept) and every problem found.

    Raises MissingColumns when the header is wrong. Rows that are empty all over are skipped.
    A category is only checked to be filled in; whether it exists is settled in a later step.
    """
    columns = _find_columns(table)
    rows: list[dict] = []
    problems: list[Problem] = []

    for position, cells in enumerate(table.rows):
        number = position + 2  # the header is row 1
        if not any(cell is not None for cell in cells):
            continue

        def cell(name: str):
            index = columns.get(name)
            return cells[index] if index is not None and index < len(cells) else None

        found: list[str] = []
        day, error = _read_date(cell("Data"), today)
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

        cents, error = _read_amount(cell("Valor"))
        if error:
            found.append(error)

        kind = parse_type(_text(cell("Tipo")))
        if kind is None:
            found.append("o tipo precisa ser Débito ou Crédito.")

        if found:
            problems.extend(Problem(number, message[0].upper() + message[1:]) for message in found)
        else:
            rows.append(
                {"row": number, "date": day.isoformat(), "label": label, "value": cents, "type": kind, "category": category}
            )
    return rows, problems

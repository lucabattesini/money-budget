import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from api.gateways.documents.base import MAX_FILE_BYTES, MAX_ROWS, Cell, Document, Table, UnreadableDocument
from api.utils.formatting import neutralize_formula

DATE_FORMAT = "DD/MM/YYYY"
AMOUNT_FORMAT = "#,##0.00"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class XlsxGateway:
    """An Excel file with real dates and real numbers (not text), so the user can sort and add them up."""

    def __init__(self, sheet_title: str = "Transações"):
        self.sheet_title = sheet_title

    def build(self, table: Table) -> Document:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = self.sheet_title

        sheet.append(table.columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"

        for row in table.rows:
            sheet.append([self._value(cell) for cell in row])
            for cell in sheet[sheet.max_row]:
                self._format(cell)

        for index, name in enumerate(table.columns, start=1):
            longest = max(
                [len(str(name))] + [len(str(row[index - 1])) for row in table.rows if row[index - 1] is not None]
            )
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = min(max(longest + 2, 10), 50)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return Document(content=buffer.getvalue(), media_type=XLSX_MEDIA_TYPE, extension="xlsx")

    @staticmethod
    def _value(cell: Cell):
        return neutralize_formula(cell) if isinstance(cell, str) else cell

    @staticmethod
    def _format(cell) -> None:
        if isinstance(cell.value, date):
            cell.number_format = DATE_FORMAT
        elif cell.value is not None and not isinstance(cell.value, str):
            cell.number_format = AMOUNT_FORMAT

    def read(self, content: bytes) -> Table:
        """The first sheet. Dates and numbers stay real dates and numbers; formulas are read as their last result."""
        if len(content) > MAX_FILE_BYTES:
            raise UnreadableDocument("O arquivo é grande demais.")
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except (zipfile.BadZipFile, KeyError, OSError, ValueError):
            raise UnreadableDocument("Não foi possível ler o arquivo Excel. Ele é mesmo um .xlsx?") from None
        try:
            sheet = workbook.worksheets[0]
            rows: list[list[Cell]] = []
            filled = 0
            for values in sheet.iter_rows(values_only=True):
                row = [self._cell(value) for value in values]
                rows.append(row)
                if any(cell is not None for cell in row):
                    filled += 1
                    if filled > MAX_ROWS + 1:  # +1: the header
                        raise UnreadableDocument(f"O arquivo tem linhas demais (o máximo é {MAX_ROWS}).")
        finally:
            workbook.close()
        while rows and all(cell is None for cell in rows[-1]):
            rows.pop()
        if not rows:
            raise UnreadableDocument("O arquivo está vazio.")
        return Table(columns=[str(cell).strip() if cell is not None else "" for cell in rows[0]], rows=rows[1:])

    @staticmethod
    def _cell(value) -> Cell:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, bool):  # a TRUE/FALSE cell is not an amount
            return str(value)
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        return value  # a date, or None

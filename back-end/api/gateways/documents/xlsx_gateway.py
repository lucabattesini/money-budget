import io
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from api.gateways.documents.base import (
    MAX_BLANK_ROWS,
    MAX_COLUMNS,
    MAX_FILE_BYTES,
    MAX_ROWS,
    Cell,
    Document,
    Table,
    UnreadableDocument,
)
from api.utils.formatting import neutralize_formula

logger = logging.getLogger(__name__)

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
        except Exception:  # not a zip, a part missing, XML that does not parse...: it is not a file we can read
            logger.warning("Could not open an Excel file", exc_info=True)
            raise UnreadableDocument("Não foi possível ler o arquivo Excel. Ele é mesmo um .xlsx?") from None
        try:
            sheet = workbook.worksheets[0]
            rows: list[list[Cell]] = []
            filled = 0
            # openpyxl pads the gaps between rows with empty ones: a file of a few KB can declare a million of them. So
            # they are counted as they come, and the width is limited too.
            for values in sheet.iter_rows(max_col=MAX_COLUMNS, values_only=True):
                row = [self._cell(value) for value in values]
                while row and row[-1] is None:  # max_col pads every row to the full width
                    row.pop()
                rows.append(row)
                filled += any(cell is not None for cell in row)
                if filled > MAX_ROWS + 1 or len(rows) > MAX_ROWS + MAX_BLANK_ROWS + 1:  # +1: the header
                    raise UnreadableDocument(f"O arquivo tem linhas demais (o máximo é {MAX_ROWS}).")
        except UnreadableDocument:
            raise
        except Exception:  # a broken sheet, no sheet at all, a number that is not one...: anything wrong with the file
            logger.warning("Could not read an Excel file", exc_info=True)
            raise UnreadableDocument("Não foi possível ler o arquivo Excel. Ele está danificado?") from None
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
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            # Excel shows 15 significant digits, and a cell that is 0.1+0.2 holds 0.30000000000000004 but shows 0.3
            return Decimal(format(value, ".15g"))
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, timedelta):  # a duration, [h]:mm
            total = int(value.total_seconds())
            return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"
        return value  # a date, or None

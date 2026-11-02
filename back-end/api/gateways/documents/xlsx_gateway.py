import io

from openpyxl import Workbook
from openpyxl.styles import Font

from api.gateways.documents.base import Cell, Document, Table
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
        if hasattr(cell.value, "year"):
            cell.number_format = DATE_FORMAT
        elif cell.value is not None and not isinstance(cell.value, str):
            cell.number_format = AMOUNT_FORMAT

import csv
import io
from datetime import date

from api.gateways.documents.base import Cell, Document, Table
from api.utils.formatting import format_amount_br, format_date_br, neutralize_formula


class CsvGateway:
    """CSV that opens correctly in Excel set to Brazilian Portuguese.

    UTF-8 with a byte order mark (so accents survive), `;` between columns (because the
    decimal separator is a comma) and Windows line endings.
    """

    delimiter = ";"

    def build(self, table: Table) -> Document:
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=self.delimiter, lineterminator="\r\n")
        writer.writerow(table.columns)
        for row in table.rows:
            writer.writerow([self._text(cell) for cell in row])
        return Document(
            content=buffer.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            extension="csv",
        )

    @staticmethod
    def _text(cell: Cell) -> str:
        if cell is None:
            return ""
        if isinstance(cell, str):
            return neutralize_formula(cell)
        if isinstance(cell, date):  # a date or a datetime
            return format_date_br(cell)
        return format_amount_br(cell)

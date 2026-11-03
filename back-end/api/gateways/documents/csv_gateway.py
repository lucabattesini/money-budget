import csv
import io
from datetime import date

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

    def read(self, content: bytes) -> Table:
        """UTF-8 (with or without the byte order mark), separated by `;` or `,`: whichever the header line uses more."""
        if len(content) > MAX_FILE_BYTES:
            raise UnreadableDocument("O arquivo é grande demais.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UnreadableDocument("O arquivo CSV precisa estar em UTF-8.") from None
        header_line = text.split("\n", 1)[0]
        if not header_line.strip():
            raise UnreadableDocument("O arquivo está vazio.")
        delimiter = ";" if header_line.count(";") >= header_line.count(",") else ","
        lines: list[list[str]] = []
        filled = 0
        try:
            for line in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter):
                lines.append(line[:MAX_COLUMNS])
                filled += any(cell.strip() for cell in line)
                # Counted while reading: five million empty lines must not be built first and refused afterwards
                if filled > MAX_ROWS + 1 or len(lines) > MAX_ROWS + MAX_BLANK_ROWS + 1:  # +1: the header
                    raise UnreadableDocument(f"O arquivo tem linhas demais (o máximo é {MAX_ROWS}).")
        except csv.Error:
            raise UnreadableDocument("Não foi possível ler o arquivo CSV.") from None
        rows = [[cell.strip() or None for cell in line] for line in lines[1:]]
        while rows and not any(rows[-1]):  # blank lines at the end are not rows
            rows.pop()
        return Table(columns=[cell.strip() for cell in lines[0]], rows=rows)

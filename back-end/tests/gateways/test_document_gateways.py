import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from api.gateways.documents import (
    SUPPORTED_FORMATS,
    CsvGateway,
    Table,
    UnreadableDocument,
    UnsupportedFormat,
    XlsxGateway,
    get_document_gateway,
)

TABLE = Table(
    columns=["Data", "Descrição", "Valor"],
    rows=[
        [date(2026, 3, 15), "Almoço", Decimal("1234.50")],
        [datetime(2026, 3, 1, 9, 30), 'Aluguel; "março"', Decimal("0.05")],
    ],
)


# --- factory -----------------------------------------------------------------


def test_the_factory_gives_the_gateway_for_each_supported_format():
    assert SUPPORTED_FORMATS == ("csv", "xlsx")
    assert isinstance(get_document_gateway("csv"), CsvGateway)
    assert isinstance(get_document_gateway("xlsx"), XlsxGateway)


@pytest.mark.parametrize("name", ["pdf", "", "CSV", "xls"])
def test_the_factory_refuses_other_formats(name):
    with pytest.raises(UnsupportedFormat):
        get_document_gateway(name)


# --- csv ---------------------------------------------------------------------


def test_csv_is_utf8_with_a_bom_so_excel_reads_the_accents():
    document = CsvGateway().build(TABLE)

    assert document.content.startswith(b"\xef\xbb\xbf")
    assert document.extension == "csv"
    assert document.media_type.startswith("text/csv")


def test_csv_uses_semicolons_brazilian_numbers_and_dates():
    text = CsvGateway().build(TABLE).content.decode("utf-8-sig")

    assert text.split("\r\n") == [
        "Data;Descrição;Valor",
        "15/03/2026;Almoço;1.234,50",
        '01/03/2026;"Aluguel; ""março""";0,05',  # quoting keeps ; and " inside a cell
        "",
    ]


def test_csv_with_no_rows_is_just_the_header():
    text = CsvGateway().build(Table(columns=["A", "B"], rows=[])).content.decode("utf-8-sig")

    assert text == "A;B\r\n"


def test_csv_leaves_missing_values_empty():
    text = CsvGateway().build(Table(columns=["A", "B"], rows=[[None, "x"]])).content.decode("utf-8-sig")

    assert text == "A;B\r\n;x\r\n"


@pytest.mark.parametrize("typed", ['=HYPERLINK("http://evil")', "+1", "-1", "@SUM(A1)"])
def test_csv_does_not_let_text_run_as_a_formula(typed):
    text = CsvGateway().build(Table(columns=["A"], rows=[[typed]])).content.decode("utf-8-sig")

    assert text.split("\r\n")[1].strip('"').startswith("'")


# --- xlsx --------------------------------------------------------------------


def _sheet(table=TABLE):
    document = XlsxGateway().build(table)
    return document, load_workbook(io.BytesIO(document.content)).active


def test_xlsx_is_an_excel_file_with_a_titled_sheet():
    document, sheet = _sheet()

    assert document.extension == "xlsx"
    assert document.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert sheet.title == "Transações"


def test_xlsx_has_a_bold_frozen_header():
    _, sheet = _sheet()

    assert [cell.value for cell in sheet[1]] == ["Data", "Descrição", "Valor"]
    assert all(cell.font.bold for cell in sheet[1])
    assert sheet.freeze_panes == "A2"


def test_xlsx_keeps_dates_and_amounts_as_real_values_with_a_format():
    _, sheet = _sheet()

    first_date, _, first_amount = sheet[2]
    assert first_date.value == datetime(2026, 3, 15)
    assert first_date.number_format == "DD/MM/YYYY"
    assert first_amount.value == 1234.5  # a number, so Excel can sort and add it
    assert first_amount.number_format == "#,##0.00"
    assert sheet["C3"].value == 0.05
    assert sheet["B3"].value == 'Aluguel; "março"'


def test_xlsx_does_not_let_text_run_as_a_formula():
    _, sheet = _sheet(Table(columns=["A"], rows=[['=HYPERLINK("http://evil")'], ["+1"]]))

    assert sheet["A2"].value.startswith("'")
    assert sheet["A2"].data_type == "s"  # stored as text, never as a formula
    assert sheet["A3"].value == "'+1"


def test_xlsx_with_no_rows_is_just_the_header():
    _, sheet = _sheet(Table(columns=["A", "B"], rows=[]))

    assert sheet.max_row == 1


# --- reading -----------------------------------------------------------------


def _xlsx(rows):
    from openpyxl import Workbook

    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("delimiter", [";", ","])
def test_csv_is_read_with_either_separator(delimiter):
    text = f"Data{delimiter}Descrição{delimiter}Valor\n15/03/2026{delimiter}Almoço{delimiter}\"1.234,50\"\n"

    table = CsvGateway().read(text.encode("utf-8"))

    assert table.columns == ["Data", "Descrição", "Valor"]
    assert table.rows == [["15/03/2026", "Almoço", "1.234,50"]]


def test_csv_written_by_the_gateway_is_read_back():
    table = CsvGateway().read(CsvGateway().build(TABLE).content)

    assert table.columns == TABLE.columns
    assert table.rows[1] == ["01/03/2026", 'Aluguel; "março"', "0,05"]


def test_csv_empty_cells_are_none_and_trailing_blank_lines_are_dropped():
    table = CsvGateway().read(b"A;B\n1;\n\n;\n")

    assert table.rows == [["1", None]]


def test_csv_blank_lines_in_the_middle_keep_their_place():
    table = CsvGateway().read(b"A;B\n1;2\n\n3;4\n")

    assert len(table.rows) == 3  # so the third data row is still row 4 of the file


def test_csv_that_is_not_utf8_is_refused():
    with pytest.raises(UnreadableDocument, match="UTF-8"):
        CsvGateway().read("Data;Descrição\n".encode("latin-1"))


def test_an_empty_csv_is_refused():
    with pytest.raises(UnreadableDocument, match="vazio"):
        CsvGateway().read(b"")


def test_csv_with_too_many_rows_or_bytes_is_refused(monkeypatch):
    from api.gateways.documents import csv_gateway

    monkeypatch.setattr(csv_gateway, "MAX_ROWS", 2)
    with pytest.raises(UnreadableDocument, match="linhas demais"):
        CsvGateway().read(b"A\n1\n2\n3\n")

    monkeypatch.setattr(csv_gateway, "MAX_FILE_BYTES", 5)
    with pytest.raises(UnreadableDocument, match="grande demais"):
        CsvGateway().read(b"A;B\n1;2\n")


def test_xlsx_keeps_real_dates_and_numbers():
    content = _xlsx([["Data", "Valor"], [datetime(2026, 3, 15), 12.5], ["  texto  ", 3]])

    table = XlsxGateway().read(content)

    assert table.columns == ["Data", "Valor"]
    assert table.rows[0] == [date(2026, 3, 15), Decimal("12.5")]
    assert table.rows[1] == ["texto", Decimal("3")]


def test_xlsx_written_by_the_gateway_is_read_back():
    table = XlsxGateway().read(XlsxGateway().build(TABLE).content)

    assert table.columns == TABLE.columns
    assert table.rows == [[date(2026, 3, 15), "Almoço", Decimal("1234.5")], [date(2026, 3, 1), 'Aluguel; "março"', Decimal("0.05")]]


def test_xlsx_blank_rows_keep_their_place():
    table = XlsxGateway().read(_xlsx([["A"], [1], [None], [3]]))

    assert len(table.rows) == 3


def test_something_that_is_not_an_xlsx_is_refused():
    with pytest.raises(UnreadableDocument, match="Excel"):
        XlsxGateway().read(b"just text, not a zip")


def test_an_xlsx_with_nothing_in_it_is_refused():
    with pytest.raises(UnreadableDocument, match="vazio"):
        XlsxGateway().read(_xlsx([]))


def test_xlsx_with_too_many_rows_is_refused(monkeypatch):
    from api.gateways.documents import xlsx_gateway

    monkeypatch.setattr(xlsx_gateway, "MAX_ROWS", 2)
    with pytest.raises(UnreadableDocument, match="linhas demais"):
        XlsxGateway().read(_xlsx([["A"], [1], [2], [3]]))

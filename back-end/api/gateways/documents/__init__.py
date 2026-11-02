from api.gateways.documents.base import Cell, Document, DocumentGateway, Table
from api.gateways.documents.csv_gateway import CsvGateway
from api.gateways.documents.xlsx_gateway import XlsxGateway

_GATEWAYS: dict[str, type] = {"csv": CsvGateway, "xlsx": XlsxGateway}

SUPPORTED_FORMATS = tuple(_GATEWAYS)


class UnsupportedFormat(ValueError):
    pass


def get_document_gateway(file_format: str) -> DocumentGateway:
    """The gateway that writes `file_format` ("csv" or "xlsx")."""
    try:
        return _GATEWAYS[file_format]()
    except KeyError:
        raise UnsupportedFormat(
            f"Unsupported document format: {file_format!r}. Use one of {SUPPORTED_FORMATS}."
        ) from None


__all__ = [
    "Cell",
    "Document",
    "DocumentGateway",
    "SUPPORTED_FORMATS",
    "Table",
    "UnsupportedFormat",
    "get_document_gateway",
]

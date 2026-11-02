"""Turns transactions into a downloadable document.

Column names are the ones the import page tells users to use, so the import can read
an exported file (after removing the apostrophe the export adds to text starting with
= + - or @, see utils/formatting.py).
"""

from decimal import Decimal

from api.gateways.documents import Document, Table, get_document_gateway
from api.utils.formatting import type_label
from schemas.tables_schemas import TransactionOut

EXPORT_COLUMNS = ["Data", "Descrição", "Categoria", "Valor", "Tipo"]


def build_transactions_table(transactions: list[TransactionOut]) -> Table:
    """One row per transaction. The amount is in reais, always positive; the direction is in Tipo."""
    return Table(
        columns=EXPORT_COLUMNS,
        rows=[
            [
                t.transactioned_at,
                t.label or "",
                t.category_name or "",
                Decimal(t.value) / 100,
                type_label(t.type),
            ]
            for t in transactions
        ],
    )


def export_transactions(transactions: list[TransactionOut], file_format: str) -> Document:
    return get_document_gateway(file_format).build(build_transactions_table(transactions))

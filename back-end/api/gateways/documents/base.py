"""What the app hands to a document gateway, and what it gets back.

A gateway turns a plain table into a file (CSV, Excel...). The rest of the app only
deals with `Table` and `Document`, so a new file type means a new gateway, nothing else.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

# What a cell may hold. Gateways decide how each one is written in their format.
Cell = str | Decimal | date | None


@dataclass(frozen=True)
class Table:
    columns: list[str]
    rows: list[list[Cell]]


@dataclass(frozen=True)
class Document:
    content: bytes
    media_type: str
    extension: str  # without the dot


class DocumentGateway(Protocol):
    def build(self, table: Table) -> Document: ...

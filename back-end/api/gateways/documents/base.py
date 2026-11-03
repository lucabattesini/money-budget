"""What the app hands to a document gateway, and what it gets back.

A gateway turns a plain table into a file (CSV, Excel...) and reads a file back into a table.
The rest of the app only deals with `Table` and `Document`, so a new file type means a new
gateway, nothing else.
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


# What a file may be before it is refused. Checked while reading, so a huge file is never loaded unchecked.
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


class UnreadableDocument(ValueError):
    """The file cannot be read at all (broken, empty, too big...). The message is meant for the person who sent it."""


class DocumentGateway(Protocol):
    def build(self, table: Table) -> Document: ...

    def read(self, content: bytes) -> Table:
        """The first row is the column names. Cells are text, numbers (Decimal) or dates; empty cells are None.
        Rows that are empty all over are kept (so a row's position is its row number in the file) but at most
        MAX_ROWS rows with something in them are accepted. Raises UnreadableDocument."""
        ...

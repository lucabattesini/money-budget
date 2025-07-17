from pydantic import BaseModel
from datetime import datetime

class TransactionsTable(BaseModel):
    id: str
    label: str
    value: float
    date: datetime
    category: str
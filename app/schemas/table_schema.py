from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List

class UpdateEntry(BaseModel):
    value: float
    date: datetime

class TransactionStatus(BaseModel):
    name: str
    value: float
    last_updated: datetime
    all_updates: List[UpdateEntry]

class TableModel(BaseModel):
    investments: Dict[str, List[TransactionStatus]]
    expenses: Dict[str, List[TransactionStatus]]
    incomes: Dict[str, List[TransactionStatus]]
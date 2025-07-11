from pydantic import BaseModel
from typing import Dict
from datetime import datetime

class MainStatus(BaseModel):
    value: float
    last_updated: datetime
    all_updates: list

class Transactions(BaseModel):
    investments: Dict[str, MainStatus]
    incomes: Dict[str, MainStatus]
    expenses: Dict[str, MainStatus]
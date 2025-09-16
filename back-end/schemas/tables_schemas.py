from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class Transaction(BaseModel):
    label: str
    value: int
    category: str
    date: Optional[datetime] = None
 
class User(BaseModel):
    name: str
    email: str 
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TransactionsDate(BaseModel):
    organized_by: Literal["day", "month", "year", "all"]
    date: Optional[datetime] = None
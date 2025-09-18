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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class UserLogin(BaseModel):
    email: str
    password: str

class GetTransactionsParams(BaseModel):
    organized_by: Optional[Literal["day", "month", "year"]] = None
    date: Optional[datetime] = None
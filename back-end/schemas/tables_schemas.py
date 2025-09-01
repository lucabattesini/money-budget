from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Transaction(BaseModel):
    label: str
    value: int
    category: str
    date: Optional[datetime] = None
 
class User(BaseModel):
    name: Optional[str] = None
    email: str 
    password: str
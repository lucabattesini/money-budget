from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class Transaction(BaseModel):
    label: str
    value: int
    category: str
    date: Optional[datetime] = None
 
class UserCreate(BaseModel):
    google_id: str
    name: str
    email: str
    picture: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    google_id: str
    name: str
    email: str
    picture: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class GetTransactionsParams(BaseModel):
    organized_by: Optional[Literal["day", "month", "year"]] = None
    date: Optional[datetime] = None
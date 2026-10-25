from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, List
from datetime import datetime, date

class Transaction(BaseModel):
    label: str
    value: int
    category_id: int
    date: Optional[datetime] = None

class TransactionFilters(BaseModel):
    """Where-clause filters shared by the transaction listing and aggregation queries."""
    start_date: Optional[date] = None  # inclusive
    end_date: Optional[date] = None  # inclusive
    category_ids: Optional[List[int]] = None
    exclude_category_ids: Optional[List[int]] = None
    search: Optional[str] = None  # case-insensitive match on the label
    min_value: Optional[int] = Field(None, ge=0)  # cents
    max_value: Optional[int] = Field(None, ge=0)  # cents
    weekdays: Optional[List[int]] = None  # 0 = Sunday ... 6 = Saturday

    @model_validator(mode="after")
    def check_ranges(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must be lower than max_value")
        if self.weekdays and any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("weekdays must be between 0 (Sunday) and 6 (Saturday)")
        return self

class TransactionOut(BaseModel):
    id: int
    label: Optional[str] = None
    value: int  # cents
    date: Optional[datetime] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None

class TransactionAggregate(BaseModel):
    # Only the key matching the group_by used is filled
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    period: Optional[str] = None  # "2026", "2026-10" or "2026-10-25"
    weekday: Optional[int] = None  # 0 = Sunday ... 6 = Saturday
    total: int  # cents
    count: int
    average: float  # cents
    max: int  # cents
 
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

class UserUpdatePhone(BaseModel):
    whatsapp_phone: str

class GetTransactionsParams(BaseModel):
    organized_by: Optional[Literal["day", "month", "year"]] = None
    date: Optional[datetime] = None
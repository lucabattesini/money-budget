from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from schemas.family_settings import Currency, Language, Timezone

# Which way the money went. `value` is always a positive amount in cents.
TransactionType = Literal["credit", "debit"]


class Transaction(BaseModel):
    label: str
    value: int
    category_id: int
    type: TransactionType = "debit"
    transactioned_at: Optional[datetime] = None  # empty means now
    user_id: Optional[int] = None  # a member of the family it belongs to; empty means the person adding it
    merchant: Optional[str] = Field(
        None, max_length=100
    )  # the place or company; only while the family has merchants on


class TransactionUpdate(BaseModel):
    """What a user may change on an existing transaction (the date stays as it was)."""

    label: str = Field(min_length=1, max_length=100)
    value: int = Field(gt=0, le=2147483647)  # cents, must fit the 32-bit column
    category_id: int
    type: Optional[TransactionType] = None  # None keeps the current type
    transactioned_at: Optional[datetime] = None  # None keeps the current date
    user_id: Optional[int] = None  # a member of the family it belongs to; None keeps the current person
    merchant: Optional[str] = Field(None, max_length=100)  # None keeps the merchant, "" takes it off


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
    merchant_ids: Optional[List[int]] = None

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
    value: int  # cents, always positive
    type: TransactionType = "debit"
    transactioned_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    user_id: Optional[int] = None  # id of the family member it belongs to
    user_name: Optional[str] = None  # and their name, for the export
    merchant_id: Optional[int] = None
    merchant_name: Optional[str] = None


class TransactionAggregate(BaseModel):
    # Only the key matching the group_by used is filled
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    merchant_id: Optional[int] = None
    merchant_name: Optional[str] = None
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


class MerchantName(BaseModel):
    name: str


class CategoryCreate(BaseModel):
    name: str
    group_id: Optional[int] = None  # empty means "Outros"


class CategoryUpdate(BaseModel):
    """What may change on a category of the family. A field left out keeps its value."""

    name: Optional[str] = None
    group_id: Optional[int] = None


class UserUpdatePhone(BaseModel):
    whatsapp_phone: str


class GetTransactionsParams(BaseModel):
    organized_by: Optional[Literal["day", "month", "year"]] = None
    date: Optional[datetime] = None

    @model_validator(mode="after")
    def _grouping_needs_a_date(self):
        if self.organized_by is not None and self.date is None:
            raise ValueError("'date' is required when 'organized_by' is set")
        return self


class FamilySettings(BaseModel):
    """What a family may change about how it sees amounts and dates; a field left out keeps its value."""

    currency: Optional[Currency] = None
    language: Optional[Language] = None
    timezone: Optional[Timezone] = None
    merchants_enabled: Optional[bool] = None


MONTH_PATTERN = r"^20\d\d-(0[1-9]|1[0-2])$"  # "2026-11"; the years 2000-2099, so every month is a valid date


class BudgetSet(BaseModel):
    """Plan an amount for a category from a month on, until a later month changes it. 0 means nothing from then on."""

    category_id: int
    month: str = Field(pattern=MONTH_PATTERN)
    amount: int = Field(ge=0, le=2147483647)  # cents, must fit the 32-bit column


class JoinFamily(BaseModel):
    code: str
    bring_data: bool  # no default: joining always asks whether to bring the old data along


ExportFormat = Literal["csv", "xlsx"]
ExportStatus = Literal["queued", "running", "done", "failed"]


class ExportJobCreate(BaseModel):
    format: ExportFormat = "csv"


class ImportColumnsChoice(BaseModel):
    """Which column of the file (its position, from 0) holds each field: {"Data": 0, "Valor": 3, "Tipo": null}."""

    mapping: dict[str, Optional[int]] = Field(max_length=20)
    # How dates written as text are read: "auto" looks at the file, then at the family's language
    date_order: Literal["auto", "day_first", "month_first", "iso"] = "auto"
    # How amounts are written: "br" is 1.234,56 and "us" is 1,234.56; "auto" accepts both
    amount_style: Literal["auto", "br", "us"] = "auto"
    # How the sign of the amount is read: always positive with the type in the Tipo column, or the sign says the direction
    sign: Literal["type_column", "negative_debit", "negative_credit"] = "type_column"


class ImportCategoriesChoice(BaseModel):
    """Which of the family's categories each category name in the file stands for: {"Pets": 12}."""

    mapping: dict[str, int] = Field(max_length=500)


class ImportPeopleChoice(BaseModel):
    """Which member of the family each person name in the file stands for: {"Bia": 7}."""

    mapping: dict[str, int] = Field(max_length=500)


class ExportJobOut(BaseModel):
    id: int
    format: ExportFormat
    status: ExportStatus
    filename: Optional[str] = None  # set once the file is ready
    error: Optional[str] = None  # set when it failed
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

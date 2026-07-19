import pydantic
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Literal

class OrchestratorResponse(BaseModel):
    message: str
    type: Literal["check", "registry", "off-topic"]

CategoryType = Literal[
    "Rent", "Utilities", "Internet & Phone", "Insurance", "Debt Payments", "Taxes", "Super Market",
    "Food", "Transportation", "Health & Pharmacy", "Personal Care", "Entertainment", "Shopping", "Subscriptions",
    "Fitness & Sports", "Hobbies", "Travel", "Education", "Home Maintenance", "Pets", "Gifts & Donations",
    "Special Events", "Emergencies", "Emergency Funds", "Investments", "Other"
]

class RecorderResponse(BaseModel):
    amount: int | None
    Category: CategoryType

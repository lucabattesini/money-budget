from pydantic import BaseModel

class Transaction(BaseModel):
    label: str
    value: int
    category: str
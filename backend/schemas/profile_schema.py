from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    email: str
    password: str
    
class UserDefaultBudget(BaseModel):
    investments: float
    incomes: float
    expenses: float
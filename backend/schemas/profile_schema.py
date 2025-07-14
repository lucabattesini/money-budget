from pydantic import BaseModel

class UserProfile(BaseModel):
    id: str
    email: str
    password: str
    name: str

class UserInvestmentsProfile(BaseModel):
    fixed_expenses: list
    fixed_earnings: list
    incertain_earnings: list
    incertain_expenses: list
    main_investment: str
    extra_investments: list
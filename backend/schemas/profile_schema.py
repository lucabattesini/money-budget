from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    email: str
    password: str
    
class UserInvestmentsProfile(BaseModel):
    fixed_expenses: list
    fixed_earnings: list
    incertain_earnings: list
    incertain_expenses: list
    main_investment: str
    extra_investments: list
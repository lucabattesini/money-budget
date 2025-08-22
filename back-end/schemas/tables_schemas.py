from pydantic import BaseModel

class Transaction(BaseModel):
    label: str
    value: int
    category: str

class User(BaseModel):
    name: str
    email: str 
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

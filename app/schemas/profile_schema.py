from pydantic import BaseModel

class UserProfile(BaseModel):
    id: str
    email: str
    password: str
    name: str
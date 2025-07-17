from pydantic import BaseModel

class CategoriesTable(BaseModel):
    id: str
    name: str
    
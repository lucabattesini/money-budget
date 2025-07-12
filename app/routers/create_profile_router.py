from fastapi import APIRouter
from app.schemas.profile_schema import UserProfile
from app.schemas.table_schema import TableModel

router = APIRouter(
    prefix="/create-profile",
    tags=["create-profile"],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def create_budget_profile(profile: UserProfile, investment_alignment: TableModel):
    return
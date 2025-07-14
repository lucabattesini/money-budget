from fastapi import APIRouter
from backend.schemas.profile_schema import UserProfile, UserInvestmentsProfile

router = APIRouter(
    prefix="/create-profile",
    tags=["create-profile"],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def create_budget_profile(profile: UserProfile, investment_alignment: UserInvestmentsProfile):
    return
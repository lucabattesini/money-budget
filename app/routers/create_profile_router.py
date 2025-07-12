from fastapi import APIRouter

router = APIRouter(
    prefix="/create-profile",
    tags=["create-profile"],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def create_budget_profile(profile: Profile, investment_alignment: TableStructure):
    return
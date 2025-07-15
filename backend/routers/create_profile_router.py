from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from schemas.profile_schema import UserProfile
from repositories.create_profile_repo import create_profile

router = APIRouter(
    prefix="/create-profile",
    tags=["create-profile"],
    responses={404: {"description": "Not found"}}
)

@router.post("/")
async def create_budget_profile(profile: UserProfile):
    create_profile(profile.name, profile.email, profile.password)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "profile created"}
    )
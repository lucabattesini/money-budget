from fastapi import APIRouter, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from api.controllers.auth_controller import login_with_google

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}}
)


class GoogleTokenRequest(BaseModel):
    id_token: str


@router.post("/google")
async def auth_google(request: GoogleTokenRequest):
    """
    Receive a Google ID token from the frontend,
    verify it, upsert the user, and return a JWT.
    """
    try:
        result = login_with_google(request.id_token)
        return JSONResponse(
            content={"data": jsonable_encoder(result)},
            status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        # google-auth raises ValueError for invalid/expired tokens
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")

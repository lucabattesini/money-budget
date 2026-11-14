from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.controllers.auth_controller import login_with_google
from db.connection import get_db

router = APIRouter(prefix="/auth", tags=["auth"], responses={404: {"description": "Not found"}})


from typing import Optional


class GoogleTokenRequest(BaseModel):
    id_token: str
    whatsapp_phone: Optional[str] = None


@router.post("/google")
def auth_google(request: GoogleTokenRequest, db: Session = Depends(get_db)):
    """
    Receive a Google ID token from the frontend,
    verify it, upsert the user, and return a JWT.
    """
    try:
        result = login_with_google(db, request.id_token, request.whatsapp_phone)
        return JSONResponse(content={"data": jsonable_encoder(result)}, status_code=status.HTTP_200_OK)
    except HTTPException:
        raise  # e.g. 409 when the WhatsApp number belongs to someone else
    except ValueError as e:
        # google-auth raises ValueError for invalid/expired tokens
        print(f"GOOGLE TOKEN VALIDATION ERROR: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")

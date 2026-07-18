from fastapi import APIRouter, status, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from controllers.users_controller import get_user_by_id_ctrl
from controllers.auth_controller import decode_jwt
from schemas.tables_schemas import UserResponse
import jwt

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)


def get_user_id_from_token(authorization: str) -> int:
    """Extract and validate JWT from Authorization header, return user_id."""
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        payload = decode_jwt(token)
        return payload["user_id"]
    except HTTPException:
        raise                           # re-raise without modification
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Authorization header malformed")



@router.get("/me", response_model=UserResponse)
async def get_me(authorization: str = Header(...)):
    """Return the currently authenticated user based on the JWT."""
    user_id = get_user_id_from_token(authorization)
    user = get_user_by_id_ctrl(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse(
        content={"data": jsonable_encoder(user)},
        status_code=status.HTTP_200_OK
    )
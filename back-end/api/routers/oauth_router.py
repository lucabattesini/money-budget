"""The sign-in of AI apps (TKT-72), in the words of OAuth 2.1 so any MCP client can use it.

The app discovers these addresses from the two `.well-known` pages, registers itself, and sends the person to
`/oauth/authorize`, which hands them to the web app's own page (where they sign in with Google as usual and say yes or
no). Then the app swaps the code for its tokens at `/oauth/token`.
"""

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.controllers.auth_controller import get_current_user_id
from api.controllers.oauth_controller import (
    OAuthError,
    check_authorization_request,
    decide,
    disconnect,
    exchange_token,
    list_connections,
    register_client,
    revoke_token,
)
from config import FRONT_URL, PUBLIC_URL
from db.connection import get_db

router = APIRouter(tags=["connector"])

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def public_url(request: Request) -> str:
    return PUBLIC_URL or str(request.base_url).rstrip("/")


def _oauth_error(error: OAuthError) -> JSONResponse:
    return JSONResponse(
        {"error": error.error, "error_description": error.description}, status_code=error.status_code, headers=NO_STORE
    )


def _protected_resource(request: Request) -> dict:
    base = public_url(request)
    return {"resource": f"{base}/mcp", "authorization_servers": [base], "bearer_methods_supported": ["header"]}


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource(request: Request):
    return _protected_resource(request)


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server(request: Request):
    base = public_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


@router.post("/oauth/register", status_code=201)
async def register(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return _oauth_error(OAuthError("invalid_client_metadata", "Send a JSON object."))
    try:
        return JSONResponse(
            jsonable_encoder(register_client(db, body.get("client_name"), body.get("redirect_uris"))),
            status_code=201,
            headers=NO_STORE,
        )
    except OAuthError as error:
        return _oauth_error(error)


@router.get("/oauth/authorize")
async def authorize(
    client_id: str = "",
    redirect_uri: str = "",
    response_type: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Where the app sends the person. Checked here, then handed to the web app's page to sign in and decide."""
    try:
        client = check_authorization_request(
            db, client_id, redirect_uri, response_type, code_challenge, code_challenge_method
        )
    except OAuthError as error:  # not sent back to the app: its address is not trusted yet
        return Response(f"{error.description}", status_code=400, media_type="text/plain")
    query = urlencode(
        {
            "client_id": client_id,
            "app": client.name,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
        }
    )
    return RedirectResponse(f"{FRONT_URL}/#/connect?{query}", status_code=302)


class Decision(BaseModel):
    client_id: str
    redirect_uri: str
    response_type: str
    code_challenge: str
    code_challenge_method: str
    state: str = ""
    allow: bool


@router.post("/oauth/authorize")
async def decide_authorization(
    body: Decision, db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)
):
    """The person's answer, sent by the web app as the signed-in person. Returns where to send them next."""
    try:
        target = decide(
            db,
            user_id,
            body.client_id,
            body.redirect_uri,
            body.response_type,
            body.code_challenge,
            body.code_challenge_method,
            body.state,
            body.allow,
        )
    except OAuthError as error:
        raise HTTPException(status_code=400, detail=error.description)
    return {"data": {"redirect_to": target}}


@router.post("/oauth/token")
async def token(request: Request, db: Session = Depends(get_db)):
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    try:
        return JSONResponse(exchange_token(db, form), headers=NO_STORE)
    except OAuthError as error:
        return _oauth_error(error)


@router.post("/oauth/revoke")
async def revoke(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    revoke_token(db, str(form.get("token") or ""), form.get("client_id"))
    return Response(status_code=200, headers=NO_STORE)


@router.get("/connections")
async def connections(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    """The AI apps the person has connected, to show them and let them disconnect."""
    return {"data": jsonable_encoder(list_connections(db, user_id))}


@router.delete("/connections/{grant_id}", status_code=204)
async def disconnect_app(grant_id: UUID, db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    if not disconnect(db, user_id, grant_id):
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")

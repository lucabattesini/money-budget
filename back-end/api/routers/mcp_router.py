"""The connector's address for AI apps (TKT-72): POST /mcp, signed in with the tokens of api/routers/oauth_router.py.

Kept apart from the rest of the API on purpose: it does not accept the web app's login, and the web app's login token
does not open it.
"""

import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.controllers.oauth_controller import authenticate_access_token
from api.controllers.users_controller import get_user_by_id_ctrl
from api.routers.oauth_router import public_url
from api.services.mcp_service import handle_message
from db.connection import get_db

router = APIRouter(tags=["connector"])

MAX_BODY_BYTES = 1024 * 1024  # 200 rows are far below this
CALLS_PER_MINUTE = 60
_recent_calls: dict[UUID, deque] = defaultdict(deque)


def _too_many_calls(grant_id: UUID) -> bool:
    """Per connection, per server copy (a limit against a runaway chat, not a quota)."""
    now = time.monotonic()
    calls = _recent_calls[grant_id]
    while calls and now - calls[0] > 60:
        calls.popleft()
    if len(calls) >= CALLS_PER_MINUTE:
        return True
    calls.append(now)
    return False


def _unauthorized(request: Request) -> Response:
    metadata = f"{public_url(request)}/.well-known/oauth-protected-resource"
    return JSONResponse(
        {"error": "invalid_token"},
        status_code=401,
        headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata}"'},
    )


@router.post("/mcp")
async def mcp(request: Request, db: Session = Depends(get_db)):
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    grant = authenticate_access_token(db, token.strip()) if scheme.lower() == "bearer" else None
    user = get_user_by_id_ctrl(db, grant.user_id) if grant else None
    if grant is None or user is None:
        return _unauthorized(request)
    if _too_many_calls(grant.id):
        return JSONResponse({"error": "Too many calls, wait a minute."}, status_code=429, headers={"Retry-After": "60"})
    declared = request.headers.get("content-length", "")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES or (declared.isdigit() and int(declared) > MAX_BODY_BYTES):
        return JSONResponse({"error": "Request too large."}, status_code=413)
    try:
        message = await request.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    answer = handle_message(db, user, message)
    if answer is None:
        return Response(status_code=202)
    return JSONResponse(answer)


@router.get("/mcp")
@router.delete("/mcp")
async def mcp_not_streaming():
    """This server never opens a stream and keeps no session, so there is nothing to GET or end."""
    return Response(status_code=405, headers={"Allow": "POST"})

from pathlib import Path

from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.gateways.documents import MAX_FILE_BYTES
from api.routers import (
    auth_router,
    budgets_router,
    categories_router,
    exports_router,
    families_router,
    imports_router,
    mcp_router,
    merchants_router,
    oauth_router,
    transactions_router,
    users_router,
    whatsapp_router,
)
from config import FRONT_URL, STATIC_DIR

# The generated API pages list every address and are of no use to the people of a deployed app, so they are only served
# in development (where the web app is not served by this server)
_serving_web_app = bool(STATIC_DIR and Path(STATIC_DIR).is_dir())
app = FastAPI(
    docs_url=None if _serving_web_app else "/docs",
    redoc_url=None if _serving_web_app else "/redoc",
    openapi_url=None if _serving_web_app else "/openapi.json",
)

UPLOAD_OVERHEAD = 1024 * 1024  # the rest of the form around the file


# The body of an upload is read before the login is checked, so a huge one is refused by its declared size first.
# (Added before CORS, so CORS wraps it and the browser can read the answer. An upload sent in chunks, with no declared
# size, is for the web server in front of the app to limit.)
@app.middleware("http")
async def refuse_huge_uploads(request, call_next):
    declared = request.headers.get("content-length", "")
    if request.method == "POST" and request.url.path.rstrip("/") == "/imports" and declared.isdigit():
        if int(declared) > MAX_FILE_BYTES + UPLOAD_OVERHEAD:
            return JSONResponse({"detail": "O arquivo é grande demais (o máximo é 5 MB)."}, status_code=413)
    if request.method == "POST" and request.url.path.rstrip("/") == "/mcp" and declared.isdigit():
        if int(declared) > mcp_router.MAX_BODY_BYTES:
            return JSONResponse({"error": "Request too large."}, status_code=413)
    if request.method == "POST" and request.url.path.startswith("/oauth/") and declared.isdigit():
        if int(declared) > oauth_router.MAX_OAUTH_BODY:  # open to anyone, so small
            return JSONResponse({"error": "invalid_request"}, status_code=413)
    response = await call_next(request)
    # Nothing legitimate puts this app in a frame (the consent page would be clickjackable)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.url.path.rstrip("/") == "/mcp":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONT_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(categories_router.router)
app.include_router(budgets_router.router)
app.include_router(merchants_router.router)
app.include_router(transactions_router.router)
app.include_router(exports_router.router)
app.include_router(imports_router.router)
app.include_router(families_router.router)
app.include_router(whatsapp_router.router)
app.include_router(oauth_router.router)
app.include_router(mcp_router.router)

# In production the same server serves the web app (a hash-routed single page, so every address is "/" plus files).
# Mounted last: every API address above wins over a file of the same name.
if _serving_web_app:
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")

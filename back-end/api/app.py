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
    merchants_router,
    transactions_router,
    users_router,
    whatsapp_router,
)
from config import FRONT_URL, STATIC_DIR

app = FastAPI()

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
    return await call_next(request)


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

# In production the same server serves the web app (a hash-routed single page, so every address is "/" plus files).
# Mounted last: every API address above wins over a file of the same name.
if STATIC_DIR and Path(STATIC_DIR).is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")

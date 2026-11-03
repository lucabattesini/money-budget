from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    auth_router,
    categories_router,
    exports_router,
    families_router,
    transactions_router,
    users_router,
    whatsapp_router,
)
from config import FRONT_URL

app = FastAPI()

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
app.include_router(transactions_router.router)
app.include_router(exports_router.router)
app.include_router(families_router.router)
app.include_router(whatsapp_router.router)

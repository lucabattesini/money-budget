import os
from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

from fastapi import FastAPI
from api.routers import categories_router, transactions_router, users_router, auth_router, whatsapp_router
from fastapi.middleware.cors import CORSMiddleware

FRONT_END_URL = os.getenv("FRONT_URL", "http://localhost:5173")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= [FRONT_END_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(categories_router.router)
app.include_router(transactions_router.router)
app.include_router(whatsapp_router.router)
from fastapi import FastAPI
from routers import categories_router, transactions_router, users_router
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

FRONT_END_URL = os.getenv("FRONT_URL")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= [FRONT_END_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(users_router.router)
app.include_router(categories_router.router)
app.include_router(transactions_router.router)
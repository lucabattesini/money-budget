from fastapi import FastAPI
from routers import create_profile_router

app = FastAPI()

app.include_router(create_profile_router.router)
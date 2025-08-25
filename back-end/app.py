from fastapi import FastAPI
from routers import categories_router, expenses_router, users_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "https://money-budget-front-end.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(users_router.router)
app.include_router(categories_router.router)
app.include_router(expenses_router.router)
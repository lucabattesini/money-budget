import os
from contextlib import contextmanager

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DB_MAX_OVERFLOW, DB_POOL_SIZE, SQL_ECHO

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DB_URL is not set. Set it in .env to a PostgreSQL URL such as "
        "postgresql+psycopg2://money:money@localhost:5432/money_budget (docker compose sets it for you)."
    )

# The password may come apart from the URL (DB_PASSWORD, from a secret manager), so the URL itself holds no secret
DB_PASSWORD = os.getenv("DB_PASSWORD")
if DB_PASSWORD:
    DATABASE_URL = make_url(DATABASE_URL).set(password=DB_PASSWORD).render_as_string(hide_password=False)

# A small pool (the database server is shared) that checks a connection is alive before using it
engine = create_engine(
    DATABASE_URL, echo=SQL_ECHO, pool_size=DB_POOL_SIZE, max_overflow=DB_MAX_OVERFLOW, pool_pre_ping=True
)

LocalSession = sessionmaker(bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: one database session per request, always closed."""
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Session for code that runs outside a request (e.g. the chatbot graph)."""
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()

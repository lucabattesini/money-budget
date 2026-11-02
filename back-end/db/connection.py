import os
from contextlib import contextmanager

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import SQL_ECHO

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DB_URL", "sqlite:///./test.db")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)

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

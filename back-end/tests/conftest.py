"""Shared test setup.

Tests run against a separate Postgres database (never the dev one). Every test
runs inside a transaction that is rolled back at the end, so tests cannot
affect each other. Gemini calls are blocked.
"""
import os

# These must be set before the app is imported: db.connection builds the engine
# and api.controllers.auth_controller reads the secret at import time.
TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+psycopg2://money:money@localhost:5432/money_budget_test",
)
os.environ["DB_URL"] = TEST_DB_URL
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ.pop("APP_ENV", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from db import connection
from schemas.tables import Categories, Users

TEST_CATEGORIES = ["Alimentação", "Transporte", "Outros"]


def _create_test_database_if_missing():
    url = make_url(TEST_DB_URL)
    assert url.database and url.database.endswith("_test"), (
        f"Refusing to run tests against '{url.database}': "
        "the test database name must end with '_test'."
    )
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create the test database and tables once, with a few fixed categories."""
    _create_test_database_if_missing()
    engine = connection.engine
    connection.Base.metadata.drop_all(engine)
    connection.Base.metadata.create_all(engine)
    with connection.LocalSession() as db:
        db.add_all(Categories(name=name) for name in TEST_CATEGORIES)
        db.commit()
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def isolated_db(database):
    """Run each test in a transaction that is rolled back afterwards.

    Sessions created by get_db() and session_scope() are bound to this
    connection; their commits become savepoints inside the outer transaction.
    """
    conn = database.connect()
    outer = conn.begin()
    original_kw = dict(connection.LocalSession.kw)
    connection.LocalSession.configure(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield conn
    finally:
        connection.LocalSession.kw.clear()
        connection.LocalSession.kw.update(original_kw)
        outer.rollback()
        conn.close()


@pytest.fixture(autouse=True)
def block_gemini(monkeypatch):
    """Fail loudly if a test tries to call the real Gemini API."""
    import google.generativeai as genai

    def blocked(*args, **kwargs):
        raise RuntimeError("Real Gemini calls are blocked in tests: mock the agent instead.")

    monkeypatch.setattr(genai.GenerativeModel, "generate_content", blocked)


@pytest.fixture
def db():
    with connection.session_scope() as session:
        yield session


@pytest.fixture
def client():
    from api.app import app

    return TestClient(app)


@pytest.fixture
def user(db):
    row = Users(google_id="google-1", name="Test User", email="test@example.com")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def other_user(db):
    row = Users(google_id="google-2", name="Other User", email="other@example.com")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def auth_headers(user):
    from api.controllers.auth_controller import create_jwt

    return {"Authorization": f"Bearer {create_jwt(user.id)}"}


@pytest.fixture
def category_id(db):
    return db.query(Categories).filter_by(name="Alimentação").one().id

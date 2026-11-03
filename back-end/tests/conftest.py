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
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test-verify-token"
# Never let a test send a real WhatsApp message, whatever the developer's .env contains
os.environ["WHATSAPP_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_ID"] = ""
os.environ.pop("APP_ENV", None)

import socket
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from db import connection
from db.seed import DEFAULT_GROUPS
from schemas.tables import Categories, CategoryGroups, Families, TransactionDB, Users

# "Pets" is deliberately NOT seeded: it is a valid category name in the agents'
# schemas, so it lets tests exercise the "known name, missing from the database" path.
TEST_CATEGORIES = ["Alimentação", "Transporte", "Supermercado", "Aluguel", "Outros"]


def _create_test_database_if_missing():
    url = make_url(TEST_DB_URL)
    assert url.database and url.database.endswith("_test"), (
        f"Refusing to run tests against '{url.database}': the test database name must end with '_test'."
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
    # drop_all runs on the app's engine, so make sure that really is the test database
    assert engine.url == make_url(TEST_DB_URL), (
        f"The app engine points at {engine.url!r}, not the test database; refusing to drop tables."
    )
    connection.Base.metadata.drop_all(engine)
    connection.Base.metadata.create_all(engine)
    with connection.LocalSession() as db:
        groups = {name: CategoryGroups(name=name) for name in DEFAULT_GROUPS}
        db.add_all(groups.values())
        db.flush()
        group_of = {category: group for group, names in DEFAULT_GROUPS.items() for category in names}
        db.add_all(Categories(name=name, group_id=groups[group_of[name]].id) for name in TEST_CATEGORIES)
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
    monkeypatch.setattr(genai.GenerativeModel, "generate_content_async", blocked)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Block outbound connections made from Python code (requests, google-auth, ...).

    The Postgres driver talks to the database through libpq, not Python sockets,
    so database access is unaffected.
    """

    def blocked(self, address, *args, **kwargs):
        raise RuntimeError(f"Network access is blocked in tests (tried to connect to {address!r}).")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture(autouse=True)
def sent_messages(monkeypatch):
    """Capture outgoing WhatsApp messages instead of sending them."""
    sent = []

    def fake_send(to_number, message_body):
        sent.append((to_number, message_body))

    monkeypatch.setattr("api.services.whatsapp_service.send_whatsapp_message", fake_send)
    monkeypatch.setattr("api.routers.whatsapp_router.send_whatsapp_message", fake_send)
    return sent


@pytest.fixture
def db():
    with connection.session_scope() as session:
        yield session


@pytest.fixture
def client():
    from api.app import app

    return TestClient(app)


@pytest.fixture
def make_user(db):
    """Create a user in a family of their own (or in `family=` when given). Each call gets a unique Google id and email."""
    counter = iter(range(1, 1000))

    def _make(name="Test User", family=None, **fields):
        n = next(counter)
        if family is None:
            family = Families()
            db.add(family)
            db.flush()
        row = Users(
            family_id=family.id,
            google_id=fields.pop("google_id", f"google-{n}"),
            name=name,
            email=fields.pop("email", f"user{n}@example.com"),
            **fields,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


@pytest.fixture
def make_transaction(db):
    """Insert a transaction directly (the create endpoint always stamps the current time)."""

    def _make(user, category_id, label="Almoço", value=2500, when=None, type="debit"):
        row = TransactionDB(
            family_id=user.family_id,
            user_id=user.id,
            label=label,
            value=value,
            transactioned_at=when or datetime.now(),
            category_id=category_id,
            type=type,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


@pytest.fixture
def headers_for():
    """Authorization headers for any user."""
    from api.controllers.auth_controller import create_jwt

    def _headers(user):
        return {"Authorization": f"Bearer {create_jwt(user.id)}"}

    return _headers


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def other_user(make_user):
    return make_user("Other User")


@pytest.fixture
def auth_headers(user, headers_for):
    return headers_for(user)


@pytest.fixture
def category_ids(db):
    """Seeded category ids by name."""
    return {c.name: c.id for c in db.query(Categories).all()}


@pytest.fixture
def category_id(db):
    return db.query(Categories).filter_by(name="Alimentação").one().id

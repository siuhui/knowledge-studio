import os
from pathlib import Path

# Load test overrides from .env.test (gitignored) — credentials and
# hostnames stay out of code.
from dotenv import load_dotenv

_test_file = Path(__file__).resolve().parent.parent / ".env.test"
if _test_file.exists():
    load_dotenv(_test_file, override=True)

os.environ.setdefault("KB_ENV", "test")

import pytest  # noqa: E402 — must follow load_dotenv + KB_ENV setdefault
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine using a separate test database."""
    test_url = "postgresql://postgres:postgres@localhost:5432/knowledgebase_test"
    engine = create_engine(test_url)

    # Ensure pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(engine):
    """Provide a transactional database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """Provide a FastAPI TestClient with overridden database dependency."""

    def override_get_db():
        yield db

    app.dependency_overrides = {}
    from app.dependencies import get_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client, db):
    """Create a test user and return auth headers for authenticated requests."""

    # Register
    client.post("/api/v1/auth/register", json={"username": "testuser", "password": "testpass123"})
    # Login
    resp = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

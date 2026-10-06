"""
Shared test setup (pytest loads this file auto)

Goals:
- Tests NEVERE touch the real Neon database or call the real AI (no cost, no risk to real data, no internet needed).
- Tests need NO real secrets, so they can run anywhere, including CI.
"""
import os

# Must happen before importing the app: the app reads these at import time.
# Plain assignment (not setdefault) overrides real values from .env, so even a mistake can't reach production data.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["API_KEY"] = "test-api-key"
os.environ["ANTHROPIC_API_KEY"] = "fake-key-never-used"
os.environ["TIMEZONE"] = "America/New_York" # fixed so results are predictable

import pytest # noqa: E402
from fastapi.testclient import TestClient # noqa: E402
from sqlalchemy.pool import StaticPool # noqa: E402
from sqlmodel import Session, SQLModel, create_engine # noqa: E402

from database import get_session # noqa: E402
from main import app # noqa: E402

@pytest.fixture
def db():
    """
    A fresh, empty in-memory database for each test.
    Every test starts from a clean slate, so tests can't affect each other.
    StaticPool + check_same_thread=False let the test client (which runs in another thread)
    share this single in-memory database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        
@pytest.fixture
def client(db):
    """
    A test client whose enpoints use the test database.
    dependency_overrides swaps get_session for our test session:
    the same dependency injection that makes the app clean also makes it testable.
    TestClient is NOT used with 'with', so the startup code (which would connect to the real database) never runs.
    """
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
    
@pytest.fixture
def auth():
    """Headers with the valid test API key."""
    return {"X-API-Key": "test-api-key"}
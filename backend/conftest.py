"""
Week 7: shared pytest fixtures for the backend test suite.

Sets fixed env vars (JWT secret, admin credentials, a throwaway sqlite
file) BEFORE importing anything from `app`, since app.database reads
DATABASE_URL at import time and app.main creates tables + seeds data at
import time too. Doing this here (rather than in tests/conftest.py) means
pytest's rootdir insertion puts `backend/` on sys.path, so test files can
just `from app.x import y` the same way the app code does internally.

Every test gets a clean, deterministic database via the `db` fixture:
drop everything, recreate the schema, reseed exactly one known admin user
and the two default policies. No test depends on state left behind by
another test, and no test depends on a randomly-generated password.
"""
import os
import tempfile

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "guardrail_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["GUARDRAIL_JWT_SECRET"] = "test-secret-do-not-use-in-prod-0123456789"
os.environ["GUARDRAIL_ADMIN_USERNAME"] = "testadmin"
os.environ["GUARDRAIL_ADMIN_PASSWORD"] = "testpass123"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import ApiKey
from app.security import generate_api_key
from app.seed_admin import seed_admin_user
from app.seed_policies import seed_default_policies

ADMIN_USERNAME = os.environ["GUARDRAIL_ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["GUARDRAIL_ADMIN_PASSWORD"]


@pytest.fixture()
def db():
    """Fresh schema per test: drop everything, recreate, reseed the known
    admin user + default policies. Yields a session for tests that need to
    read/write the DB directly (most tests just go through the API)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_admin_user(session)
        seed_default_policies(session)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    """A logged-in dashboard session for the seeded admin user."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def agent_api_key(db):
    """Creates one API key scoped to agent_id='test-agent' directly in the
    DB (bypassing the dashboard, since tests just need a credential) and
    returns the raw key for use in the X-API-Key header."""
    raw_key, key_hash = generate_api_key()
    db.add(ApiKey(agent_id="test-agent", label="test key", key_hash=key_hash))
    db.commit()
    return raw_key


@pytest.fixture()
def agent_headers(agent_api_key):
    return {"X-API-Key": agent_api_key}


def make_event(**overrides):
    """A minimal valid ToolCallEventIn payload, with any fields overridden."""
    payload = {
        "event_id": "evt-1",
        "session_id": "sess-1",
        "agent_id": "test-agent",
        "tool_name": "get_balance",
        "arguments": {"account": "ACC1234"},
    }
    payload.update(overrides)
    return payload

"""
Auth: dashboard login (JWT) and agent credentials (API key), plus the two
`require_*` dependencies that gate every other route.
"""
from conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_login_succeeds_with_correct_credentials(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_fails_with_wrong_password(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": ADMIN_USERNAME, "password": "not-the-password"},
    )
    assert resp.status_code == 401


def test_login_fails_for_unknown_user(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_login_error_identical_for_bad_user_and_bad_password(client):
    """Distinguishing 'no such user' from 'wrong password' would let an
    attacker enumerate valid usernames - both must fail the same way."""
    r1 = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    r2 = client.post("/api/v1/auth/login", json={"username": ADMIN_USERNAME, "password": "x"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_me_requires_a_session(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_the_logged_in_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == ADMIN_USERNAME


def test_me_rejects_a_garbage_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_me_rejects_a_missing_bearer_prefix(client, auth_headers):
    raw_token = auth_headers["Authorization"].split(" ", 1)[1]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": raw_token})
    assert resp.status_code == 401


def test_agent_route_requires_api_key(client):
    resp = client.post("/api/v1/events", json={
        "event_id": "e1", "session_id": "s1", "agent_id": "a1",
        "tool_name": "get_balance", "arguments": {},
    })
    assert resp.status_code == 401


def test_agent_route_rejects_invalid_api_key(client):
    resp = client.post(
        "/api/v1/events",
        json={"event_id": "e1", "session_id": "s1", "agent_id": "a1", "tool_name": "get_balance", "arguments": {}},
        headers={"X-API-Key": "gk_this_key_does_not_exist"},
    )
    assert resp.status_code == 401


def test_agent_route_rejects_revoked_api_key(client, db, agent_headers):
    from app.models import ApiKey
    from datetime import datetime, timezone

    key_row = db.query(ApiKey).filter(ApiKey.agent_id == "test-agent").one()
    key_row.revoked_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.post(
        "/api/v1/events",
        json={"event_id": "e1", "session_id": "s1", "agent_id": "test-agent", "tool_name": "get_balance", "arguments": {}},
        headers=agent_headers,
    )
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"]

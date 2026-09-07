"""
Events API: the Policy Engine -> Risk Engine -> Decision Engine pipeline,
exercised through the real HTTP endpoints (not by calling the engines
directly) so these tests also cover auth, serialization, and persistence -
not just decision logic in isolation.

Relies on the two default policies seeded by conftest's `db` fixture:
  - block-user-deletion:  delete_user -> BLOCK, always
  - high-value-transfer:  transfer_money, amount > 5000 -> REQUIRE_APPROVAL
"""
from conftest import make_event


def test_allowed_call_returns_allow_and_is_persisted(client, agent_headers):
    resp = client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "ALLOW"
    assert body["event_id"] == "evt-1"


def test_blocked_tool_returns_block(client, agent_headers):
    resp = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-2", tool_name="delete_user", arguments={"user_id": "u1"}),
        headers=agent_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "BLOCK"
    assert body["policy_result"] == "block-user-deletion"


def test_high_value_transfer_requires_approval(client, agent_headers):
    resp = client.post(
        "/api/v1/events",
        json=make_event(
            event_id="evt-3",
            tool_name="transfer_money",
            arguments={"amount": 25000, "account": "ACC9999"},
        ),
        headers=agent_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert body["policy_result"] == "high-value-transfer"


def test_low_value_transfer_is_allowed(client, agent_headers):
    resp = client.post(
        "/api/v1/events",
        json=make_event(
            event_id="evt-4",
            tool_name="transfer_money",
            arguments={"amount": 100, "account": "ACC1234"},
        ),
        headers=agent_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "ALLOW"


def test_duplicate_event_id_is_rejected(client, agent_headers):
    client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    resp = client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    assert resp.status_code == 409


def test_agent_cannot_report_event_for_a_different_agent_id(client, agent_headers):
    """The API key is scoped to agent_id='test-agent' - it must not be
    usable to report events under any other agent's name."""
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="someone-elses-agent"),
        headers=agent_headers,
    )
    assert resp.status_code == 403


def test_report_result_updates_the_event(client, agent_headers):
    client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    resp = client.post(
        "/api/v1/events/evt-1/result",
        json={"event_id": "evt-1", "execution_status": "SUCCESS", "result": {"balance": 42}},
        headers=agent_headers,
    )
    assert resp.status_code == 200


def test_report_result_for_unknown_event_is_404(client, agent_headers):
    resp = client.post(
        "/api/v1/events/does-not-exist/result",
        json={"event_id": "does-not-exist", "execution_status": "SUCCESS"},
        headers=agent_headers,
    )
    assert resp.status_code == 404


def test_report_result_rejects_cross_agent_event(client, db, agent_headers):
    """A second agent's key must not be able to attach a result to the
    first agent's event."""
    from app.models import ApiKey
    from app.security import generate_api_key

    raw_key, key_hash = generate_api_key()
    db.add(ApiKey(agent_id="other-agent", key_hash=key_hash))
    db.commit()

    client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    resp = client.post(
        "/api/v1/events/evt-1/result",
        json={"event_id": "evt-1", "execution_status": "SUCCESS"},
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 403


def test_list_events_requires_dashboard_login(client):
    resp = client.get("/api/v1/events")
    assert resp.status_code == 401


def test_list_events_rejects_an_api_key(client, agent_headers):
    """An agent's API key authenticates machine writes, not dashboard
    reads - list_events is a human-only endpoint."""
    resp = client.get("/api/v1/events", headers=agent_headers)
    assert resp.status_code == 401


def test_list_events_returns_recorded_events(client, agent_headers, auth_headers):
    client.post("/api/v1/events", json=make_event(), headers=agent_headers)
    resp = client.get("/api/v1/events", headers=auth_headers)
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["event_id"] == "evt-1"

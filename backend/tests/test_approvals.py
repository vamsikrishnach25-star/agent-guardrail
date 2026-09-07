"""
Approvals: the human-in-the-loop queue, and specifically the Week 6 fix -
`decided_by` must come from the authenticated dashboard session, never
from anything the client puts in the request body.
"""
from conftest import ADMIN_USERNAME, make_event


def _create_pending_approval(client, agent_headers, event_id="evt-1"):
    resp = client.post(
        "/api/v1/events",
        json=make_event(event_id=event_id, tool_name="transfer_money", arguments={"amount": 99999, "account": "ACC0"}),
        headers=agent_headers,
    )
    assert resp.json()["decision"] == "REQUIRE_APPROVAL"


def test_list_approvals_requires_login(client):
    resp = client.get("/api/v1/approvals")
    assert resp.status_code == 401


def test_pending_approval_appears_in_the_queue(client, agent_headers, auth_headers):
    _create_pending_approval(client, agent_headers)
    resp = client.get("/api/v1/approvals?status=PENDING", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["event_id"] == "evt-1"
    assert rows[0]["status"] == "PENDING"


def test_approve_records_the_session_user_as_decided_by(client, agent_headers, auth_headers):
    _create_pending_approval(client, agent_headers)
    approval_id = client.get("/api/v1/approvals", headers=auth_headers).json()[0]["id"]

    resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "looks fine"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["decided_by"] == ADMIN_USERNAME
    assert body["decision_reason"] == "looks fine"


def test_decided_by_ignores_a_client_supplied_value(client, agent_headers, auth_headers):
    """The old, insecure behavior let the caller pass decided_by directly.
    Even if a client still sends that field, it must be ignored - only the
    authenticated session's username can end up in the audit trail."""
    _create_pending_approval(client, agent_headers)
    approval_id = client.get("/api/v1/approvals", headers=auth_headers).json()[0]["id"]

    resp = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "ok", "decided_by": "someone-else"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["decided_by"] == ADMIN_USERNAME


def test_deny_marks_the_approval_denied(client, agent_headers, auth_headers):
    _create_pending_approval(client, agent_headers)
    approval_id = client.get("/api/v1/approvals", headers=auth_headers).json()[0]["id"]

    resp = client.post(f"/api/v1/approvals/{approval_id}/deny", json={"reason": "too risky"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "DENIED"


def test_cannot_decide_an_approval_twice(client, agent_headers, auth_headers):
    _create_pending_approval(client, agent_headers)
    approval_id = client.get("/api/v1/approvals", headers=auth_headers).json()[0]["id"]

    client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=auth_headers)
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=auth_headers)
    assert resp.status_code == 409


def test_by_event_requires_an_api_key_not_a_login(client, agent_headers, auth_headers):
    _create_pending_approval(client, agent_headers)
    resp = client.get("/api/v1/approvals/by-event/evt-1", headers=auth_headers)
    assert resp.status_code == 401


def test_by_event_returns_the_matching_approval_for_its_own_agent(client, agent_headers):
    _create_pending_approval(client, agent_headers)
    resp = client.get("/api/v1/approvals/by-event/evt-1", headers=agent_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


def test_by_event_blocks_polling_another_agents_approval(client, db, agent_headers):
    _create_pending_approval(client, agent_headers)

    from app.models import ApiKey
    from app.security import generate_api_key

    raw_key, key_hash = generate_api_key()
    db.add(ApiKey(agent_id="other-agent", key_hash=key_hash))
    db.commit()

    resp = client.get("/api/v1/approvals/by-event/evt-1", headers={"X-API-Key": raw_key})
    assert resp.status_code == 403

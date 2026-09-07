"""
Integration-level Week 9 coverage: condition_dsl policies actually driving
real decisions through the events API (not just the evaluator in
isolation - see test_policy_dsl.py for that), the legacy simpleeval
`condition` string still working unchanged, DSL validation errors
surfacing as a 400 from the API, and the new POST /api/v1/policies/simulate
dry-run endpoint.
"""
from conftest import make_event


def test_seeded_high_value_transfer_uses_condition_dsl(client, auth_headers):
    policy = next(
        p for p in client.get("/api/v1/policies", headers=auth_headers).json()
        if p["name"] == "high-value-transfer"
    )
    assert policy["condition_dsl"] == {"field": "arguments.amount", "op": "gt", "value": 5000}
    assert policy["condition"] is None


def test_condition_dsl_policy_drives_a_real_decision(client, agent_headers):
    """The seeded high-value-transfer policy is now condition_dsl-based -
    prove it still actually triggers REQUIRE_APPROVAL through the real
    events pipeline, not just in the unit-level evaluator tests."""
    resp = client.post(
        "/api/v1/events",
        json=make_event(tool_name="transfer_money", arguments={"amount": 50000, "account": "ACC9999"}),
        headers=agent_headers,
    )
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert body["policy_result"] == "high-value-transfer"


def test_legacy_condition_string_still_works_end_to_end(client, auth_headers, agent_headers):
    """Backward compatibility: a policy created with the old flat
    simpleeval `condition` string (no condition_dsl at all) must still
    correctly drive a decision - Week 9 didn't require migrating anything
    that already existed."""
    client.post(
        "/api/v1/policies",
        json={
            "name": "legacy-style-block",
            "tool_name": "issue_refund",
            "condition": "amount > 1000",
            "action": "BLOCK",
            "priority": 5,
        },
        headers=auth_headers,
    )

    allowed = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-legacy-allow", tool_name="issue_refund", arguments={"amount": 50}),
        headers=agent_headers,
    )
    assert allowed.json()["decision"] == "ALLOW"

    blocked = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-legacy-block", tool_name="issue_refund", arguments={"amount": 5000}),
        headers=agent_headers,
    )
    assert blocked.json()["decision"] == "BLOCK"
    assert blocked.json()["policy_result"] == "legacy-style-block"


def test_create_policy_rejects_malformed_condition_dsl(client, auth_headers):
    resp = client.post(
        "/api/v1/policies",
        json={
            "name": "bad-dsl-policy",
            "tool_name": "get_balance",
            "condition_dsl": {"field": "arguments.amount", "op": "not-a-real-op", "value": 1},
            "action": "BLOCK",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "invalid condition_dsl" in resp.json()["detail"]


def test_update_policy_also_validates_condition_dsl(client, auth_headers):
    policy = client.post(
        "/api/v1/policies",
        json={"name": "will-be-broken", "tool_name": "get_balance", "action": "ALLOW"},
        headers=auth_headers,
    ).json()

    resp = client.patch(
        f"/api/v1/policies/{policy['id']}",
        json={
            "name": "will-be-broken", "tool_name": "get_balance", "action": "ALLOW",
            "condition_dsl": {"all": []},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_combinator_dsl_policy_via_api(client, auth_headers, agent_headers):
    """A condition the legacy string format genuinely couldn't express
    cleanly: block a transfer that is either very large OR going to one
    specific flagged account - an OR across two different fields."""
    client.post(
        "/api/v1/policies",
        json={
            "name": "flagged-or-huge-transfer",
            "tool_name": "transfer_money",
            "condition_dsl": {"any": [
                {"field": "arguments.amount", "op": "gt", "value": 100000},
                {"field": "arguments.account", "op": "eq", "value": "ACC_FLAGGED"},
            ]},
            "action": "BLOCK",
            "priority": 1,
        },
        headers=auth_headers,
    )

    huge = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-huge", tool_name="transfer_money", arguments={"amount": 200000, "account": "ACC1234"}),
        headers=agent_headers,
    )
    assert huge.json()["decision"] == "BLOCK"

    flagged = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-flagged", tool_name="transfer_money", arguments={"amount": 1, "account": "ACC_FLAGGED"}),
        headers=agent_headers,
    )
    assert flagged.json()["decision"] == "BLOCK"

    neither = client.post(
        "/api/v1/events",
        json=make_event(event_id="evt-neither", tool_name="transfer_money", arguments={"amount": 1, "account": "ACC1234"}),
        headers=agent_headers,
    )
    assert neither.json()["decision"] == "ALLOW"


# ---- POST /api/v1/policies/simulate ----

def test_simulate_requires_login(client):
    resp = client.post("/api/v1/policies/simulate", json={"tool_name": "get_balance", "arguments": {}})
    assert resp.status_code == 401


def test_simulate_does_not_persist_anything(client, auth_headers):
    resp = client.post(
        "/api/v1/policies/simulate",
        json={"tool_name": "delete_user", "agent_id": "whoever", "arguments": {"user_id": "u1"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "BLOCK"
    assert body["matched_policies"] == ["block-user-deletion"]

    # nothing should have been written to the events table
    events = client.get("/api/v1/events", headers=auth_headers).json()
    assert events == []


def test_simulate_reports_matched_policies_and_risk(client, auth_headers):
    resp = client.post(
        "/api/v1/policies/simulate",
        json={"tool_name": "transfer_money", "arguments": {"amount": 50000, "account": "ACC9999"}},
        headers=auth_headers,
    )
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert "high-value-transfer" in body["matched_policies"]
    assert body["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")


def test_simulate_allowed_call(client, auth_headers):
    resp = client.post(
        "/api/v1/policies/simulate",
        json={"tool_name": "get_balance", "arguments": {"account": "ACC1234"}},
        headers=auth_headers,
    )
    body = resp.json()
    assert body["decision"] == "ALLOW"
    assert body["matched_policies"] == []

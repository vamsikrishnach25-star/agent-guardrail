"""Policies CRUD API - all routes require a logged-in dashboard user."""


def test_list_policies_requires_login(client):
    resp = client.get("/api/v1/policies")
    assert resp.status_code == 401


def test_list_policies_returns_the_seeded_defaults(client, auth_headers):
    resp = client.get("/api/v1/policies", headers=auth_headers)
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"block-user-deletion", "high-value-transfer"}


def test_create_policy(client, auth_headers):
    resp = client.post(
        "/api/v1/policies",
        json={"name": "block-export", "tool_name": "export_customer_data", "action": "BLOCK"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "block-export"


def test_create_policy_rejects_invalid_action(client, auth_headers):
    resp = client.post(
        "/api/v1/policies",
        json={"name": "bad-policy", "tool_name": "x", "action": "MAYBE"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_policy_rejects_duplicate_name(client, auth_headers):
    payload = {"name": "block-user-deletion", "tool_name": "delete_user", "action": "BLOCK"}
    resp = client.post("/api/v1/policies", json=payload, headers=auth_headers)
    assert resp.status_code == 409


def test_update_policy(client, auth_headers):
    policy = client.get("/api/v1/policies", headers=auth_headers).json()[0]
    resp = client.patch(
        f"/api/v1/policies/{policy['id']}",
        json={**{k: policy[k] for k in ("name", "tool_name", "action", "priority", "enabled")}, "enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_delete_policy(client, auth_headers):
    policy = client.get("/api/v1/policies", headers=auth_headers).json()[0]
    resp = client.delete(f"/api/v1/policies/{policy['id']}", headers=auth_headers)
    assert resp.status_code == 200

    remaining = client.get("/api/v1/policies", headers=auth_headers).json()
    assert policy["id"] not in [p["id"] for p in remaining]


def test_disabling_a_policy_stops_it_from_matching(client, auth_headers, agent_headers):
    policy = next(
        p for p in client.get("/api/v1/policies", headers=auth_headers).json()
        if p["name"] == "block-user-deletion"
    )
    client.patch(
        f"/api/v1/policies/{policy['id']}",
        json={**policy, "enabled": False},
        headers=auth_headers,
    )

    from conftest import make_event
    resp = client.post(
        "/api/v1/events",
        json=make_event(tool_name="delete_user", arguments={"user_id": "u1"}),
        headers=agent_headers,
    )
    assert resp.json()["decision"] == "ALLOW"

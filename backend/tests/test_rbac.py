"""
Week 11: user account management (routers/users.py) and the ADMIN/
APPROVER/VIEWER permission matrix across the rest of the API.
"""
from conftest import ADMIN_USERNAME, make_event


# ---- seeded admin ----

def test_seeded_admin_has_admin_role(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["role"] == "ADMIN"


# ---- user management: create ----

def test_create_user_requires_admin(client):
    resp = client.post("/api/v1/users", json={"username": "x", "password": "y", "role": "VIEWER"})
    assert resp.status_code == 401


def test_create_user(client, auth_headers):
    resp = client.post(
        "/api/v1/users",
        json={"username": "newviewer", "password": "pw123456", "role": "VIEWER"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "newviewer"
    assert body["role"] == "VIEWER"
    assert "password" not in body and "password_hash" not in body


def test_create_user_rejects_invalid_role(client, auth_headers):
    resp = client.post(
        "/api/v1/users",
        json={"username": "bad", "password": "pw123456", "role": "SUPERUSER"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_user_rejects_duplicate_username(client, auth_headers):
    client.post("/api/v1/users", json={"username": "dupe", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers)
    resp = client.post("/api/v1/users", json={"username": "dupe", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers)
    assert resp.status_code == 409


def test_new_user_can_actually_log_in(client, auth_headers):
    client.post("/api/v1/users", json={"username": "loginable", "password": "correcthorse", "role": "VIEWER"}, headers=auth_headers)
    resp = client.post("/api/v1/auth/login", json={"username": "loginable", "password": "correcthorse"})
    assert resp.status_code == 200


# ---- user management: list ----

def test_list_users_requires_admin(client, viewer_headers):
    resp = client.get("/api/v1/users", headers=viewer_headers)
    assert resp.status_code == 403


def test_list_users_includes_role(client, auth_headers):
    client.post("/api/v1/users", json={"username": "listed", "password": "pw123456", "role": "APPROVER"}, headers=auth_headers)
    resp = client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    users = {u["username"]: u["role"] for u in resp.json()}
    assert users["listed"] == "APPROVER"
    assert users[ADMIN_USERNAME] == "ADMIN"


# ---- user management: role changes ----

def test_update_role_requires_admin(client, viewer_headers, auth_headers):
    target = client.post("/api/v1/users", json={"username": "target1", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers).json()
    resp = client.patch(f"/api/v1/users/{target['id']}/role", json={"role": "APPROVER"}, headers=viewer_headers)
    assert resp.status_code == 403


def test_admin_can_promote_a_viewer_to_approver(client, auth_headers):
    target = client.post("/api/v1/users", json={"username": "target2", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers).json()
    resp = client.patch(f"/api/v1/users/{target['id']}/role", json={"role": "APPROVER"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "APPROVER"


def test_cannot_demote_the_last_admin(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    resp = client.patch(f"/api/v1/users/{me['id']}/role", json={"role": "VIEWER"}, headers=auth_headers)
    assert resp.status_code == 409


def test_can_demote_an_admin_if_another_admin_remains(client, auth_headers):
    second_admin = client.post("/api/v1/users", json={"username": "second-admin", "password": "pw123456", "role": "ADMIN"}, headers=auth_headers).json()
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    resp = client.patch(f"/api/v1/users/{me['id']}/role", json={"role": "VIEWER"}, headers=auth_headers)
    assert resp.status_code == 200


def test_update_role_rejects_invalid_role(client, auth_headers):
    target = client.post("/api/v1/users", json={"username": "target3", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers).json()
    resp = client.patch(f"/api/v1/users/{target['id']}/role", json={"role": "SUPERUSER"}, headers=auth_headers)
    assert resp.status_code == 400


def test_update_role_for_unknown_user_is_404(client, auth_headers):
    resp = client.patch("/api/v1/users/does-not-exist/role", json={"role": "VIEWER"}, headers=auth_headers)
    assert resp.status_code == 404


# ---- user management: delete ----

def test_admin_cannot_delete_own_account(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    resp = client.delete(f"/api/v1/users/{me['id']}", headers=auth_headers)
    assert resp.status_code == 400


def test_deleting_a_non_admin_target_succeeds(client, auth_headers):
    target = client.post("/api/v1/users", json={"username": "target4", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers).json()
    resp = client.delete(f"/api/v1/users/{target['id']}", headers=auth_headers)
    assert resp.status_code == 200


def test_deleting_an_admin_is_fine_if_another_admin_remains(client, auth_headers):
    second_admin_headers = _login_as(client, auth_headers, "second-admin-2", "ADMIN")
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    resp = client.delete(f"/api/v1/users/{me['id']}", headers=second_admin_headers)
    assert resp.status_code == 200

    remaining = client.get("/api/v1/users", headers=second_admin_headers).json()
    assert [u for u in remaining if u["role"] == "ADMIN"] and me["id"] not in [u["id"] for u in remaining]


def test_delete_requires_admin(client, viewer_headers, auth_headers):
    target = client.post("/api/v1/users", json={"username": "target5", "password": "pw123456", "role": "VIEWER"}, headers=auth_headers).json()
    resp = client.delete(f"/api/v1/users/{target['id']}", headers=viewer_headers)
    assert resp.status_code == 403


def _login_as(client, auth_headers, username, role):
    client.post("/api/v1/users", json={"username": username, "password": "pw123456", "role": role}, headers=auth_headers)
    login = client.post("/api/v1/auth/login", json={"username": username, "password": "pw123456"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ---- permission matrix: VIEWER ----

def test_viewer_can_read_events_policies_approvals_keys(client, viewer_headers):
    assert client.get("/api/v1/events", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/policies", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/approvals", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/keys", headers=viewer_headers).status_code == 200


def test_viewer_can_simulate_a_policy(client, viewer_headers):
    resp = client.post(
        "/api/v1/policies/simulate",
        json={"tool_name": "get_balance", "arguments": {"account": "ACC1234"}},
        headers=viewer_headers,
    )
    assert resp.status_code == 200


def test_viewer_cannot_approve_or_deny(client, viewer_headers, agent_headers):
    client.post(
        "/api/v1/events",
        json=make_event(tool_name="transfer_money", arguments={"amount": 99999, "account": "ACC0"}),
        headers=agent_headers,
    )
    approval_id = client.get("/api/v1/approvals", headers=viewer_headers).json()[0]["id"]
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=viewer_headers)
    assert resp.status_code == 403


def test_viewer_cannot_write_policies(client, viewer_headers):
    resp = client.post(
        "/api/v1/policies",
        json={"name": "viewer-attempt", "tool_name": "x", "action": "BLOCK"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403


def test_viewer_cannot_mint_keys(client, viewer_headers):
    resp = client.post("/api/v1/keys", json={"agent_id": "viewer-attempt"}, headers=viewer_headers)
    assert resp.status_code == 403


def test_viewer_cannot_manage_users(client, viewer_headers):
    resp = client.post("/api/v1/users", json={"username": "x", "password": "y", "role": "VIEWER"}, headers=viewer_headers)
    assert resp.status_code == 403


# ---- permission matrix: APPROVER ----

def test_approver_can_approve_and_deny(client, approver_headers, agent_headers):
    client.post(
        "/api/v1/events",
        json=make_event(tool_name="transfer_money", arguments={"amount": 99999, "account": "ACC0"}),
        headers=agent_headers,
    )
    approval_id = client.get("/api/v1/approvals", headers=approver_headers).json()[0]["id"]
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=approver_headers)
    assert resp.status_code == 200
    assert resp.json()["decided_by"] == "testapprover"


def test_approver_cannot_write_policies(client, approver_headers):
    resp = client.post(
        "/api/v1/policies",
        json={"name": "approver-attempt", "tool_name": "x", "action": "BLOCK"},
        headers=approver_headers,
    )
    assert resp.status_code == 403


def test_approver_cannot_mint_keys(client, approver_headers):
    resp = client.post("/api/v1/keys", json={"agent_id": "approver-attempt"}, headers=approver_headers)
    assert resp.status_code == 403


def test_approver_cannot_manage_users(client, approver_headers):
    resp = client.get("/api/v1/users", headers=approver_headers)
    assert resp.status_code == 403


# ---- permission matrix: ADMIN (superset check) ----

def test_admin_can_do_everything_approver_and_viewer_can(client, auth_headers, agent_headers):
    assert client.get("/api/v1/events", headers=auth_headers).status_code == 200
    assert client.post(
        "/api/v1/policies", json={"name": "admin-can", "tool_name": "x", "action": "ALLOW"}, headers=auth_headers
    ).status_code == 200
    assert client.post("/api/v1/keys", json={"agent_id": "admin-can"}, headers=auth_headers).status_code == 200

    client.post(
        "/api/v1/events",
        json=make_event(tool_name="transfer_money", arguments={"amount": 99999, "account": "ACC0"}),
        headers=agent_headers,
    )
    approval_id = client.get("/api/v1/approvals", headers=auth_headers).json()[0]["id"]
    assert client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=auth_headers).status_code == 200

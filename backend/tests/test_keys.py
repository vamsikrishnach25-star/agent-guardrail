"""API key management - minting/listing/revoking agent credentials, all
gated by a dashboard login (never a separate 'admin' credential type)."""


def test_list_keys_requires_login(client):
    resp = client.get("/api/v1/keys")
    assert resp.status_code == 401


def test_create_key_returns_the_raw_key_once(client, auth_headers):
    resp = client.post("/api/v1/keys", json={"agent_id": "billing-agent"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == "billing-agent"
    assert body["raw_key"].startswith("gk_")
    # key_preview is derived from the stored hash, not the raw key, so it
    # never reflects even a fragment of the actual secret back to the caller.
    assert body["key_preview"].startswith("...")
    assert body["raw_key"][-6:] not in body["key_preview"]


def test_created_key_is_not_returned_raw_again_on_list(client, auth_headers):
    create_resp = client.post("/api/v1/keys", json={"agent_id": "billing-agent"}, headers=auth_headers)
    raw_key = create_resp.json()["raw_key"]

    list_resp = client.get("/api/v1/keys", headers=auth_headers)
    assert list_resp.status_code == 200
    for key in list_resp.json():
        assert "raw_key" not in key
        assert raw_key not in str(key)


def test_new_key_actually_authenticates(client, auth_headers):
    raw_key = client.post("/api/v1/keys", json={"agent_id": "billing-agent"}, headers=auth_headers).json()["raw_key"]

    from conftest import make_event
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="billing-agent"),
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200


def test_revoked_key_stops_authenticating(client, auth_headers):
    created = client.post("/api/v1/keys", json={"agent_id": "billing-agent"}, headers=auth_headers).json()
    client.post(f"/api/v1/keys/{created['id']}/revoke", headers=auth_headers)

    from conftest import make_event
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="billing-agent"),
        headers={"X-API-Key": created["raw_key"]},
    )
    assert resp.status_code == 401

"""
Week 10: coverage for the support_agent/ domain's seeded policies and
seeding functions. conftest.py's `db` fixture already calls
seed_support_policies/seed_support_api_key are NOT wired into the test
fixture automatically (only seed_admin_user + seed_default_policies are -
see conftest.py) - these tests call the seed functions directly, which
also happens to be exactly what proves they're safe to call standalone
and are idempotent, the whole point of writing them the way main.py does.
"""
from sqlalchemy import select

from app.models import ApiKey, Policy
from app.seed_admin import seed_support_api_key
from app.seed_policies import seed_support_policies
from conftest import make_event


def test_seed_support_policies_creates_all_three(db):
    seed_support_policies(db)
    names = {
        row.name for row in db.execute(
            select(Policy).where(Policy.tool_name.in_(["issue_refund", "close_ticket"]))
        ).scalars()
    }
    assert names == {"fraudulent-refund-block", "high-value-refund-approval", "vip-ticket-closure-approval"}


def test_seed_support_policies_is_idempotent(db):
    seed_support_policies(db)
    seed_support_policies(db)
    count = db.execute(select(Policy.id).where(Policy.name == "high-value-refund-approval")).all()
    assert len(count) == 1


def test_seed_support_policies_does_not_overwrite_an_edited_policy(db):
    """If an admin has already edited a support policy (e.g. disabled it),
    a later restart must not silently re-enable it - upsert-by-name only
    creates what's missing, never touches what already exists."""
    seed_support_policies(db)
    policy = db.execute(select(Policy).where(Policy.name == "fraudulent-refund-block")).scalar_one()
    policy.enabled = False
    db.commit()

    seed_support_policies(db)
    refreshed = db.execute(select(Policy).where(Policy.name == "fraudulent-refund-block")).scalar_one()
    assert refreshed.enabled is False


def test_seed_support_api_key_creates_one_key_for_support_agent(db):
    seed_support_api_key(db)
    keys = db.execute(select(ApiKey).where(ApiKey.agent_id == "support-agent")).scalars().all()
    assert len(keys) == 1


def test_seed_support_api_key_is_idempotent(db):
    seed_support_api_key(db)
    seed_support_api_key(db)
    keys = db.execute(select(ApiKey).where(ApiKey.agent_id == "support-agent")).scalars().all()
    assert len(keys) == 1


# ---- the seeded policies actually driving decisions, via the real events API ----

def _support_agent_headers(db):
    """A fresh API key for agent_id='support-agent', independent of
    seed_support_api_key (that's tested above on its own) - keeps these
    decision tests from depending on seeding order."""
    from app.security import generate_api_key
    raw_key, key_hash = generate_api_key()
    db.add(ApiKey(agent_id="support-agent", label="test", key_hash=key_hash))
    db.commit()
    return {"X-API-Key": raw_key}


def test_small_refund_is_allowed(client, db):
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="issue_refund", arguments={"amount": 500, "ticket_id": "TCK-1001"}),
        headers=headers,
    )
    assert resp.json()["decision"] == "ALLOW"


def test_medium_refund_requires_approval(client, db):
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="issue_refund", arguments={"amount": 3000, "ticket_id": "TCK-1001"}),
        headers=headers,
    )
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert body["policy_result"] == "high-value-refund-approval"


def test_huge_refund_is_blocked_not_just_pended(client, db):
    """Above the fraud threshold, the BLOCK policy must win over the
    REQUIRE_APPROVAL one that also matches (amount > 2000 AND > 20000) -
    decision_engine.py's most-restrictive-wins rule."""
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="issue_refund", arguments={"amount": 50000, "ticket_id": "TCK-1003"}),
        headers=headers,
    )
    body = resp.json()
    assert body["decision"] == "BLOCK"
    assert body["policy_result"] == "fraudulent-refund-block"


def test_closing_a_standard_ticket_is_allowed(client, db):
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="close_ticket", arguments={"ticket_id": "TCK-1001", "tier": "standard"}),
        headers=headers,
    )
    assert resp.json()["decision"] == "ALLOW"


def test_closing_a_vip_ticket_requires_approval(client, db):
    """The DSL condition compares a string field (tier == 'VIP'), not a
    number - the kind of comparison the legacy simpleeval string format
    handled far more awkwardly."""
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="close_ticket", arguments={"ticket_id": "TCK-1002", "tier": "VIP"}),
        headers=headers,
    )
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert body["policy_result"] == "vip-ticket-closure-approval"


def test_escalation_has_no_policy_and_is_allowed_by_default(client, db):
    """No policy targets escalate_to_manager at all - it should fall
    through to the risk-engine safety net, and since nothing about this
    call looks risky, that means a plain ALLOW."""
    seed_support_policies(db)
    headers = _support_agent_headers(db)
    resp = client.post(
        "/api/v1/events",
        json=make_event(agent_id="support-agent", tool_name="escalate_to_manager", arguments={"ticket_id": "TCK-1001", "reason": "angry customer"}),
        headers=headers,
    )
    body = resp.json()
    assert body["decision"] == "ALLOW"
    assert body["policy_result"] is None

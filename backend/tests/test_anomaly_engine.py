"""
Week 12: tests for anomaly_engine.py directly (unit-level, seeding Event
rows straight into the DB) plus one end-to-end test through the real
events API, the same "hit the real HTTP layer" philosophy the rest of
this suite uses (see conftest.py's docstring and test_events.py).
"""
import uuid

from app.anomaly_engine import AMOUNT_FLOOR, MIN_HISTORY, detect_anomaly
from app.models import Event


def _seed_events(db, agent_id: str, n: int, tool_name: str = "get_balance", amount=None, risk_score: float = 5.0):
    for _ in range(n):
        arguments = {"account": "ACC1234"}
        if amount is not None:
            arguments["amount"] = amount
        db.add(Event(
            event_id=str(uuid.uuid4()), session_id="s1", agent_id=agent_id,
            tool_name=tool_name, arguments=arguments,
            risk_score=risk_score, risk_level="LOW", decision="ALLOW",
        ))
    db.commit()


def test_cold_start_is_not_anomalous(db):
    _seed_events(db, "cold-agent", MIN_HISTORY - 1)
    result = detect_anomaly(db, "cold-agent", "get_balance", {"account": "ACC1234"}, 5)
    assert result.is_anomaly is False
    assert result.score == 0
    assert "not enough history" in result.reason


def test_repeat_of_normal_behavior_is_not_flagged(db):
    _seed_events(db, "steady-agent", MIN_HISTORY + 10)
    result = detect_anomaly(db, "steady-agent", "get_balance", {"account": "ACC1234"}, 5)
    assert result.is_anomaly is False


def test_never_before_seen_tool_is_flagged(db):
    _seed_events(db, "one-trick-agent", MIN_HISTORY + 5, tool_name="get_balance")
    result = detect_anomaly(db, "one-trick-agent", "export_report", {}, 5)
    assert result.is_anomaly is True
    assert result.score == 100
    assert "never been called by this agent before" in result.reason


def test_amount_far_above_historical_average_is_flagged(db):
    _seed_events(db, "spender-agent", MIN_HISTORY + 5, tool_name="transfer_money", amount=100, risk_score=10)
    result = detect_anomaly(db, "spender-agent", "transfer_money", {"account": "ACC1234", "amount": 50000}, 60)
    assert result.is_anomaly is True
    assert result.score == 100
    assert "historical average" in result.reason


def test_amount_below_floor_does_not_trigger_the_rule_even_if_proportionally_large(db):
    """A tiny historical average (e.g. 10) times a 5x jump only reaches 50 -
    below AMOUNT_FLOOR, so this must not trip the deterministic amount rule
    even though it's proportionally a big jump. Guards against nuisance
    flags on agents that only ever deal in small amounts."""
    _seed_events(db, "small-spender", MIN_HISTORY + 5, tool_name="transfer_money", amount=10, risk_score=5)
    result = detect_anomaly(db, "small-spender", "transfer_money", {"account": "ACC1234", "amount": 50}, 10)
    assert 50 < AMOUNT_FLOOR
    assert "historical average" not in result.reason


def test_different_agents_have_independent_baselines(db):
    """agent-a's history must not affect what looks normal for agent-b -
    each agent's baseline is scoped to its own agent_id (see the WHERE
    clause in detect_anomaly)."""
    _seed_events(db, "agent-a", MIN_HISTORY + 5, tool_name="get_balance")
    # agent-b has never called anything - cold start, not "agent-a's tool is normal"
    result = detect_anomaly(db, "agent-b", "get_balance", {"account": "ACC1234"}, 5)
    assert result.is_anomaly is False
    assert "not enough history" in result.reason


def test_end_to_end_through_the_real_events_api_requires_approval(client, agent_headers):
    """Seeds normal history for test-agent through the real
    POST /api/v1/events endpoint (not a DB shortcut), then sends one call
    to a tool this agent has never used - asserts the API's own decision
    is REQUIRE_APPROVAL and that the response surfaces anomaly info, not
    just that detect_anomaly() in isolation would have flagged it."""
    for i in range(MIN_HISTORY + 5):
        resp = client.post(
            "/api/v1/events",
            json={
                "event_id": f"history-{i}",
                "session_id": "s1",
                "agent_id": "test-agent",
                "tool_name": "get_balance",
                "arguments": {"account": "ACC1234"},
            },
            headers=agent_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision"] == "ALLOW"

    resp = client.post(
        "/api/v1/events",
        json={
            "event_id": "the-odd-one-out",
            "session_id": "s1",
            "agent_id": "test-agent",
            "tool_name": "export_report",
            "arguments": {},
        },
        headers=agent_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "REQUIRE_APPROVAL"
    assert body["anomaly_score"] == 100
    assert body["anomaly_is_anomaly"] is True
    assert "export_report" in body["anomaly_reason"]

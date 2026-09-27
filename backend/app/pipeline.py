"""
Week 9: the policy -> risk -> decision pipeline, factored out of
routers/events.py so it can be reused by the policy dry-run endpoint
(routers/policies.py) without one router importing another's internals or
duplicating this logic. `report_tool_call` (the real, persisted path) and
`simulate_policy` (the dry-run, nothing-persisted path) now both call this
one function - there's exactly one place a tool call gets turned into a
decision, same principle decision_engine.py's own docstring makes about
itself.

Week 12: adds the Anomaly Engine as a third input alongside policy and
risk. It needs `agent_id` and database access (to look at that agent's
own history), both of which this function already had - anomaly detection
slots in as one more step, not a parallel pipeline. When `agent_id` is
absent (the simulate endpoint defaults to a synthetic "simulated-agent"
with no real history) it still runs, it just always reports "not enough
history yet" via anomaly_engine's own cold-start guard - simulate stays a
true dry-run either way.
"""
from typing import Optional

from sqlalchemy.orm import Session

from .anomaly_engine import detect_anomaly
from .decision_engine import decide as run_decision_engine
from .policy_engine import evaluate_policies
from .risk_engine import calculate_risk


def run_pipeline(db: Session, tool_name: str, agent_id: Optional[str], arguments: dict) -> dict:
    policy_matches = evaluate_policies(db, tool_name, arguments, agent_id=agent_id)
    risk = calculate_risk(tool_name, arguments)
    anomaly = detect_anomaly(db, agent_id or "simulated-agent", tool_name, arguments, risk.score)
    outcome = run_decision_engine(policy_matches, risk, anomaly)

    return {
        "decision": outcome.decision,
        "policy_result": outcome.policy_result,
        "risk_score": risk.score,
        "risk_level": risk.level,
        "reason": outcome.reason,
        "risk_factors": risk.factors,
        "matched_policies": [m.policy_name for m in policy_matches],
        "anomaly_score": anomaly.score,
        "anomaly_is_anomaly": anomaly.is_anomaly,
        "anomaly_reason": anomaly.reason,
    }

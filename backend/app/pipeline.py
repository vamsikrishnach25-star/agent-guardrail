"""
Week 9: the policy -> risk -> decision pipeline, factored out of
routers/events.py so it can be reused by the policy dry-run endpoint
(routers/policies.py) without one router importing another's internals or
duplicating this logic. `report_tool_call` (the real, persisted path) and
`simulate_policy` (the dry-run, nothing-persisted path) now both call this
one function - there's exactly one place a tool call gets turned into a
decision, same principle decision_engine.py's own docstring makes about
itself.
"""
from typing import Optional

from sqlalchemy.orm import Session

from .decision_engine import decide as run_decision_engine
from .policy_engine import evaluate_policies
from .risk_engine import calculate_risk


def run_pipeline(db: Session, tool_name: str, agent_id: Optional[str], arguments: dict) -> dict:
    policy_matches = evaluate_policies(db, tool_name, arguments, agent_id=agent_id)
    risk = calculate_risk(tool_name, arguments)
    outcome = run_decision_engine(policy_matches, risk)

    return {
        "decision": outcome.decision,
        "policy_result": outcome.policy_result,
        "risk_score": risk.score,
        "risk_level": risk.level,
        "reason": outcome.reason,
        "risk_factors": risk.factors,
        "matched_policies": [m.policy_name for m in policy_matches],
    }

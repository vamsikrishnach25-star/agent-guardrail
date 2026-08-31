"""
Policy Engine.

Answers exactly one question: "does this action violate a configured rule?"
It does NOT know or care how risky the action is - that's the Risk Engine's
job (see risk_engine.py). Keeping these separate means a rule like
"delete_user is always blocked" doesn't have to be re-expressed as a risk
score, and risk scoring doesn't have to be re-expressed as a rule.

Policies are rows in the `policies` table, not hardcoded in this file -
an admin (Week 7 dashboard) can add/edit/disable them without a deploy.

Condition strings are evaluated with simpleeval, a restricted expression
evaluator - NOT Python's eval(). eval() would let a malicious or malformed
policy string execute arbitrary code inside a system whose entire job is
to stop unauthorized actions. simpleeval only allows arithmetic/boolean/
comparison expressions against the names we explicitly pass in.
"""
from dataclasses import dataclass
from typing import Optional

from simpleeval import simple_eval, InvalidExpression
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Policy


@dataclass
class PolicyMatch:
    policy_name: str
    action: str  # ALLOW | BLOCK | REQUIRE_APPROVAL
    condition: Optional[str]


def _condition_matches(condition: Optional[str], arguments: dict) -> bool:
    if not condition:
        return True  # no condition => applies to every call of this tool
    try:
        return bool(simple_eval(condition, names=arguments))
    except InvalidExpression:
        # Malformed policy condition - fail safe: treat as non-match rather
        # than crashing the whole decision pipeline over one bad policy.
        return False
    except Exception:
        # e.g. condition references an argument this tool call didn't pass
        # (KeyError inside simpleeval) - also treated as non-match.
        return False


def evaluate_policies(db: Session, tool_name: str, arguments: dict) -> list[PolicyMatch]:
    """Return every enabled policy whose tool_name + condition match this call,
    ordered by priority (lower number = evaluated/reported first)."""
    rows = db.execute(
        select(Policy)
        .where(Policy.tool_name == tool_name, Policy.enabled == True)  # noqa: E712
        .order_by(Policy.priority.asc())
    ).scalars().all()

    matches = []
    for row in rows:
        if _condition_matches(row.condition, arguments):
            matches.append(PolicyMatch(policy_name=row.name, action=row.action, condition=row.condition))
    return matches

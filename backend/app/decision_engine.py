"""
Decision Engine.

Combines Policy Engine output + Risk Engine output into exactly one of
ALLOW / BLOCK / REQUIRE_APPROVAL. This is the only place that produces a
final decision - Policy and Risk each contribute an input, neither one
unilaterally decides.

Precedence, most restrictive wins:
    1. Any matching policy says BLOCK           -> BLOCK
    2. Any matching policy says REQUIRE_APPROVAL -> REQUIRE_APPROVAL
    3. No policy matched, but risk is HIGH/CRITICAL -> REQUIRE_APPROVAL
       (a safety net for actions nobody's written a policy for yet)
    4. Otherwise                                  -> ALLOW
"""
from dataclasses import dataclass
from typing import Optional

from .policy_engine import PolicyMatch
from .risk_engine import RiskAssessment


@dataclass
class Decision:
    decision: str  # ALLOW | BLOCK | REQUIRE_APPROVAL
    policy_result: Optional[str]  # human-readable summary of which policy drove this, if any
    reason: str


def decide(policy_matches: list[PolicyMatch], risk: RiskAssessment) -> Decision:
    blocking = [m for m in policy_matches if m.action == "BLOCK"]
    if blocking:
        m = blocking[0]
        return Decision(decision="BLOCK", policy_result=m.policy_name,
                         reason=f"blocked by policy '{m.policy_name}'")

    approval_required = [m for m in policy_matches if m.action == "REQUIRE_APPROVAL"]
    if approval_required:
        m = approval_required[0]
        return Decision(decision="REQUIRE_APPROVAL", policy_result=m.policy_name,
                         reason=f"policy '{m.policy_name}' requires approval")

    if risk.level in ("HIGH", "CRITICAL"):
        return Decision(decision="REQUIRE_APPROVAL", policy_result=None,
                         reason=f"no matching policy, but risk is {risk.level} ({risk.score}/100)")

    policy_result = policy_matches[0].policy_name if policy_matches else None
    return Decision(decision="ALLOW", policy_result=policy_result, reason="no blocking conditions")

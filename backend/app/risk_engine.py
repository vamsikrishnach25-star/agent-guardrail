"""
Risk Engine.

Answers a different question from the Policy Engine: "how risky is this
action?" - a continuous score, not a yes/no rule match. An action can have
zero matching policies and still be CRITICAL risk (e.g. a brand-new tool
nobody's written a policy for yet); the Decision Engine uses that as a
safety net.

Score is additive across independent factors (0-100, capped). This mirrors
the worked example in the project write-up:
    High-value transaction    +30
    Financial operation       +20
    New recipient             +20
    Sensitive account action  +25

Week 9 (Anomaly Detection) adds a behavioral factor here (unusual sequence/
frequency, via Isolation Forest) - it plugs in as one more factor function,
nothing else about this module changes.
"""
from dataclasses import dataclass, field

FINANCIAL_TOOLS = {"transfer_money", "issue_refund", "download_statement"}
SENSITIVE_TOOLS = {"delete_user", "delete_customer", "export_customer_data"}
HIGH_VALUE_THRESHOLD = 10_000
TRUSTED_ACCOUNTS = {"ACC1234"}  # demo stand-in for a real "known recipients" store


@dataclass
class RiskAssessment:
    score: int
    level: str
    factors: list[str] = field(default_factory=list)


def _factor_high_value(tool_name: str, arguments: dict):
    amount = arguments.get("amount")
    if isinstance(amount, (int, float)) and amount > HIGH_VALUE_THRESHOLD:
        return 30, f"high-value transaction (amount={amount} > {HIGH_VALUE_THRESHOLD})"
    return 0, None


def _factor_financial_operation(tool_name: str, arguments: dict):
    if tool_name in FINANCIAL_TOOLS:
        return 20, "financial operation"
    return 0, None


def _factor_new_recipient(tool_name: str, arguments: dict):
    account = arguments.get("account")
    if tool_name in FINANCIAL_TOOLS and account and account not in TRUSTED_ACCOUNTS:
        return 20, f"new/unrecognized recipient ({account})"
    return 0, None


def _factor_sensitive_tool(tool_name: str, arguments: dict):
    if tool_name in SENSITIVE_TOOLS:
        return 25, "sensitive account operation"
    return 0, None


FACTORS = [_factor_high_value, _factor_financial_operation, _factor_new_recipient, _factor_sensitive_tool]


def _classify(score: int) -> str:
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    if score <= 80:
        return "HIGH"
    return "CRITICAL"


def calculate_risk(tool_name: str, arguments: dict) -> RiskAssessment:
    score = 0
    factors: list[str] = []
    for factor_fn in FACTORS:
        points, reason = factor_fn(tool_name, arguments)
        if points:
            score += points
            factors.append(f"+{points} {reason}")
    score = min(score, 100)
    return RiskAssessment(score=score, level=_classify(score), factors=factors)

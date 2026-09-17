"""
Week 10: toy tools for the customer-support agent - the second demo agent,
built specifically to prove Guardrail is reusable infrastructure and not a
one-off script wired to the finance domain (see support_agent.py and the
README for why this exists). Same pattern as demo_agent/tools.py: these
simulate what would normally be real API calls into a support platform.
"""

TICKETS = {
    "TCK-1001": {"tier": "standard", "status": "open"},
    "TCK-1002": {"tier": "VIP", "status": "open"},
    "TCK-1003": {"tier": "standard", "status": "open"},
}


def issue_refund(amount: float, ticket_id: str) -> dict:
    if ticket_id not in TICKETS:
        raise ValueError(f"unknown ticket {ticket_id}")
    return {"ticket_id": ticket_id, "amount": amount, "status": "refunded"}


def close_ticket(ticket_id: str, tier: str = "standard") -> dict:
    """`tier` is passed in explicitly by the caller (not looked up
    internally) specifically so the Policy Engine can see it - a policy
    only ever sees what's in the call's `arguments`, not a tool's internal
    state, so context the policy needs to reason about has to be part of
    the call itself. See the vip-ticket-closure-approval policy."""
    if ticket_id not in TICKETS:
        raise ValueError(f"unknown ticket {ticket_id}")
    TICKETS[ticket_id]["status"] = "closed"
    return {"ticket_id": ticket_id, "tier": tier, "status": "closed"}


def escalate_to_manager(ticket_id: str, reason: str) -> dict:
    if ticket_id not in TICKETS:
        raise ValueError(f"unknown ticket {ticket_id}")
    return {"ticket_id": ticket_id, "reason": reason, "status": "escalated"}

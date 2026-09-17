"""
Seeds a couple of default policies on first startup, purely so the demo
agent has something to demonstrate out of the box. This is NOT how policies
should be managed long-term - the dashboard (and the /api/v1/policies API)
let an admin create/edit/disable policies without touching code. Only
seeds if the table is empty, so it never clobbers policies you've created
or edited since.

Week 9: `high-value-transfer` is written using the new structured
condition_dsl (see policy_dsl.py) as the flagship example of the new
format - it's equivalent to the old `condition="amount > 5000"` string,
kept below in a comment so the before/after is easy to compare. The
legacy string format still works unchanged (see policy_engine.py and
backend/tests/test_policy_dsl.py's backward-compat test); it just isn't
what new policies are seeded with anymore.

Week 10: `seed_support_policies()` below is a second, separate seed
function for the support_agent/ demo - deliberately NOT using the
"only if the table is empty" pattern `seed_default_policies` uses. That
pattern works for a brand-new install, but the already-live Render
deployment's `policies` table is not empty (it already has the finance
policies plus whatever's been created since) - an "only if empty" seed
would never run there, silently leaving support_agent broken in
production. Instead it upserts each support policy by name, so it's safe
to call on every startup regardless of what's already in the table: a new
install gets all 5 policies, and an existing deployment picks up exactly
the 3 new ones on its next deploy, without touching anything else.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Policy

DEFAULT_POLICIES = [
    dict(
        name="block-user-deletion",
        tool_name="delete_user",
        condition=None,
        action="BLOCK",
        priority=10,
        description="User deletion is never allowed through an agent - always blocked.",
    ),
    dict(
        name="high-value-transfer",
        tool_name="transfer_money",
        # equivalent legacy form: condition="amount > 5000"
        condition_dsl={"field": "arguments.amount", "op": "gt", "value": 5000},
        action="REQUIRE_APPROVAL",
        priority=10,
        description="Transfers over 5,000 need a human to sign off before executing.",
    ),
]

# Week 10: policies for the second demo agent (support_agent/) - a
# different domain (customer support, not finance) on purpose, to prove
# these are genuinely reusable, generic mechanisms and not something built
# to fit one specific set of tools.
SUPPORT_POLICIES = [
    dict(
        name="fraudulent-refund-block",
        tool_name="issue_refund",
        condition_dsl={"field": "arguments.amount", "op": "gt", "value": 20000},
        action="BLOCK",
        priority=5,
        description="Refunds this large are always blocked outright - treated as a likely fraud pattern, not something a human should even need to approve.",
    ),
    dict(
        name="high-value-refund-approval",
        tool_name="issue_refund",
        condition_dsl={"field": "arguments.amount", "op": "gt", "value": 2000},
        action="REQUIRE_APPROVAL",
        priority=10,
        description="Refunds over 2,000 need a human to sign off before executing.",
    ),
    dict(
        name="vip-ticket-closure-approval",
        tool_name="close_ticket",
        condition_dsl={"field": "arguments.tier", "op": "eq", "value": "VIP"},
        action="REQUIRE_APPROVAL",
        priority=10,
        description="Closing a VIP customer's ticket needs a human's sign-off - a good example of a condition the legacy string format couldn't express as cleanly (comparing a string field, not a number).",
    ),
]


def seed_default_policies(db: Session) -> None:
    existing = db.execute(select(Policy.id).limit(1)).first()
    if existing:
        return
    for p in DEFAULT_POLICIES:
        db.add(Policy(**p))
    db.commit()


def seed_support_policies(db: Session) -> None:
    """Upserts each support_agent policy by name - safe to call on every
    startup, unlike seed_default_policies' 'only if empty' check. Never
    overwrites a policy that already exists (so edits made via the
    dashboard survive a restart), only creates the ones that are missing."""
    for p in SUPPORT_POLICIES:
        existing = db.execute(select(Policy.id).where(Policy.name == p["name"])).scalar_one_or_none()
        if existing:
            continue
        db.add(Policy(**p))
    db.commit()

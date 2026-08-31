"""
Seeds a couple of default policies on first startup, purely so the demo
agent has something to demonstrate out of the box. This is NOT how policies
should be managed long-term - Week 7's dashboard (and the /api/v1/policies
API added this week) let an admin create/edit/disable policies without
touching code. Only seeds if the table is empty, so it never clobbers
policies you've created or edited since.
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
        condition="amount > 5000",
        action="REQUIRE_APPROVAL",
        priority=10,
        description="Transfers over 5,000 need a human to sign off before executing.",
    ),
]


def seed_default_policies(db: Session) -> None:
    existing = db.execute(select(Policy.id).limit(1)).first()
    if existing:
        return
    for p in DEFAULT_POLICIES:
        db.add(Policy(**p))
    db.commit()

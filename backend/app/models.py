"""
SQLAlchemy models.

Week 1: events table.
Week 2: policies table (configurable rules - never hardcoded).
Week 3: approvals table (the human-approval queue).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, Boolean
from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=_uuid)
    event_id = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    agent_id = Column(String, index=True, nullable=False)

    event_type = Column(String, nullable=False, default="TOOL_CALL")
    tool_name = Column(String, index=True, nullable=False)
    arguments = Column(JSON, nullable=False, default=dict)

    # Filled in during Week 1: always ALLOW. Weeks 2-4 wire in real values.
    policy_result = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    decision = Column(String, nullable=False, default="ALLOW")

    execution_status = Column(String, nullable=True)  # SUCCESS / FAILURE / BLOCKED / PENDING
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class Policy(Base):
    """
    A configurable rule the Policy Engine evaluates against every tool call.

    `condition` is an optional boolean expression evaluated against the
    call's arguments dict (e.g. "amount > 5000"). If null/empty, the policy
    matches every call to `tool_name` unconditionally. Evaluated with
    simpleeval, NOT Python's eval() - arbitrary code execution in a safety
    product would be an obvious own-goal.
    """
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, unique=True, nullable=False)
    tool_name = Column(String, index=True, nullable=False)
    condition = Column(String, nullable=True)  # e.g. "amount > 5000"
    action = Column(String, nullable=False)     # ALLOW | BLOCK | REQUIRE_APPROVAL
    priority = Column(Integer, nullable=False, default=100)  # lower runs first
    enabled = Column(Boolean, nullable=False, default=True)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Approval(Base):
    """
    The human-approval queue. One row per event that the Decision Engine
    flagged REQUIRE_APPROVAL.

    Engineering note: the write-up calls for Redis as the approval queue
    ("real-time / temporary state"). This implementation deliberately uses
    the same relational database instead (Postgres in prod, SQLite in dev):
    at this project's scale a polled DB table gives identical behavior with
    one less moving part to install/run, and the schema below is exactly
    what you'd lift into Redis (or Postgres LISTEN/NOTIFY for push instead
    of poll) if you needed multi-instance fan-out later. Worth being able
    to explain this trade-off, not hide it.
    """
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=_uuid)
    event_id = Column(String, unique=True, index=True, nullable=False)

    agent_id = Column(String, nullable=False)
    session_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSON, nullable=False, default=dict)

    policy_result = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    reason = Column(String, nullable=True)

    status = Column(String, nullable=False, default="PENDING")  # PENDING | APPROVED | DENIED
    decided_by = Column(String, nullable=True)
    decision_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)

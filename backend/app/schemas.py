"""Pydantic request/response schemas for the events API."""
from typing import Any, Optional
from pydantic import BaseModel


class ToolCallEventIn(BaseModel):
    event_id: str
    session_id: str
    agent_id: str
    event_type: str = "TOOL_CALL"
    tool_name: str
    arguments: dict[str, Any] = {}


class DecisionOut(BaseModel):
    event_id: str
    decision: str          # ALLOW | BLOCK | REQUIRE_APPROVAL
    policy_result: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    reason: Optional[str] = None
    risk_factors: list[str] = []


class ToolResultIn(BaseModel):
    event_id: str
    execution_status: str  # SUCCESS | FAILURE
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class PolicyIn(BaseModel):
    name: str
    tool_name: str
    condition: Optional[str] = None
    action: str  # ALLOW | BLOCK | REQUIRE_APPROVAL
    priority: int = 100
    enabled: bool = True
    description: Optional[str] = None


class PolicyOut(PolicyIn):
    id: str

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: str
    event_id: str
    agent_id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    policy_result: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    reason: Optional[str] = None
    status: str
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class ApprovalDecisionIn(BaseModel):
    decided_by: str
    reason: Optional[str] = None

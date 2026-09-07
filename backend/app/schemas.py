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
    condition: Optional[str] = None            # legacy: simpleeval expression string
    condition_dsl: Optional[dict[str, Any]] = None  # Week 9: structured condition tree, see policy_dsl.py
    action: str  # ALLOW | BLOCK | REQUIRE_APPROVAL
    priority: int = 100
    enabled: bool = True
    description: Optional[str] = None


class PolicyOut(PolicyIn):
    id: str

    model_config = {"from_attributes": True}


class PolicySimulateIn(BaseModel):
    """Week 9: dry-run a hypothetical tool call against the currently
    configured policies - nothing gets persisted, so an admin can check
    what a policy (new or existing) would actually do before it goes
    live."""
    tool_name: str
    agent_id: str = "simulated-agent"
    arguments: dict[str, Any] = {}


class PolicySimulateOut(BaseModel):
    decision: str
    policy_result: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    reason: Optional[str] = None
    risk_factors: list[str] = []
    matched_policies: list[str] = []


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
    # Week 6: `decided_by` is no longer client-supplied - it comes from the
    # authenticated dashboard session (see routers/approvals.py), so a
    # human can't type someone else's name into the audit trail. Only the
    # free-text reason is still theirs to provide.
    reason: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    expires_in_seconds: int


class UserOut(BaseModel):
    id: str
    username: str

    model_config = {"from_attributes": True}


class ApiKeyIn(BaseModel):
    agent_id: str
    label: Optional[str] = None


class ApiKeyOut(BaseModel):
    id: str
    agent_id: str
    label: Optional[str] = None
    created_at: str
    revoked_at: Optional[str] = None
    key_preview: str  # last 6 chars only, e.g. "...a1B2c3" - never the full key again


class ApiKeyCreatedOut(ApiKeyOut):
    # Only present in the response to the creation call - the raw key is
    # shown exactly once and cannot be retrieved again after this.
    raw_key: str

"""
Approvals API - the human-in-the-loop queue.

    GET  /api/v1/approvals               - list approvals (optionally ?status=PENDING)
    GET  /api/v1/approvals/by-event/{id} - the SDK polls this to find out if/when
                                            a human has decided (see sdk/guardrail_sdk/interceptor.py)
    POST /api/v1/approvals/{id}/approve  - human approves
    POST /api/v1/approvals/{id}/deny     - human denies

Approving/denying here does not itself execute or block the tool - it just
records the decision. The SDK (which is still holding the paused call,
polling) is what acts on it: executes the tool if APPROVED, raises if
DENIED. That keeps "who's allowed to execute tools" entirely inside the
SDK boundary, not scattered across this API.

Week 6: two different credential types on this router, matching who's
actually calling each endpoint. `by-event/{id}` is polled by the SDK
(agent-side) while it waits for a decision, so it takes an API key - and
only returns an approval that belongs to that key's own agent_id, so one
agent can't poll another agent's pending approvals. Everything else here
(listing the queue, approving, denying) is a human action from the
dashboard, so it requires a logged-in user instead. `decided_by` is no
longer something the caller types in - it's the authenticated username.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_agent, require_user
from ..database import get_db
from ..models import ApiKey, Approval, User
from ..schemas import ApprovalDecisionIn

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _serialize(a: Approval) -> dict:
    return {
        "id": a.id,
        "event_id": a.event_id,
        "agent_id": a.agent_id,
        "session_id": a.session_id,
        "tool_name": a.tool_name,
        "arguments": a.arguments,
        "policy_result": a.policy_result,
        "risk_score": a.risk_score,
        "risk_level": a.risk_level,
        "reason": a.reason,
        "status": a.status,
        "decided_by": a.decided_by,
        "decision_reason": a.decision_reason,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
    }


@router.get("")
def list_approvals(status: str | None = None, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    stmt = select(Approval).order_by(Approval.created_at.desc())
    if status:
        stmt = stmt.where(Approval.status == status.upper())
    rows = db.execute(stmt).scalars().all()
    return [_serialize(a) for a in rows]


@router.get("/by-event/{event_id}")
def get_by_event(event_id: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_agent)):
    a = db.execute(select(Approval).where(Approval.event_id == event_id)).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="no approval found for this event_id")
    if a.agent_id != api_key.agent_id:
        raise HTTPException(status_code=403, detail="this API key cannot poll another agent's approval")
    return _serialize(a)


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    decision_in: ApprovalDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="approval not found")
    if a.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"approval already {a.status}")
    a.status = "APPROVED"
    a.decided_by = current_user.username
    a.decision_reason = decision_in.reason
    a.decided_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize(a)


@router.post("/{approval_id}/deny")
def deny(
    approval_id: str,
    decision_in: ApprovalDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    a = db.get(Approval, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="approval not found")
    if a.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"approval already {a.status}")
    a.status = "DENIED"
    a.decided_by = current_user.username
    a.decision_reason = decision_in.reason
    a.decided_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize(a)

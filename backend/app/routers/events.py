"""
Events API.

    POST /api/v1/events             - SDK reports a tool call, gets a decision back
    POST /api/v1/events/{id}/result - SDK reports the tool's execution outcome
    GET  /api/v1/events              - list recent events (dashboard uses this)

Week 2: `decide()` now runs the real pipeline - Policy Engine, then Risk
Engine, then Decision Engine combines both. The API contract (DecisionOut)
is unchanged from Week 1 on purpose: the SDK and any future caller don't
need to know or care what's inside decide().
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, Approval
from ..schemas import ToolCallEventIn, DecisionOut, ToolResultIn
from ..policy_engine import evaluate_policies
from ..risk_engine import calculate_risk
from ..decision_engine import decide as run_decision_engine

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def decide(db: Session, event_in: ToolCallEventIn) -> dict:
    policy_matches = evaluate_policies(db, event_in.tool_name, event_in.arguments)
    risk = calculate_risk(event_in.tool_name, event_in.arguments)
    outcome = run_decision_engine(policy_matches, risk)

    return {
        "decision": outcome.decision,
        "policy_result": outcome.policy_result,
        "risk_score": risk.score,
        "risk_level": risk.level,
        "reason": outcome.reason,
        "risk_factors": risk.factors,
    }


@router.post("", response_model=DecisionOut)
def report_tool_call(event_in: ToolCallEventIn, db: Session = Depends(get_db)):
    existing = db.execute(
        select(Event).where(Event.event_id == event_in.event_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="event_id already exists")

    outcome = decide(db, event_in)

    event = Event(
        event_id=event_in.event_id,
        session_id=event_in.session_id,
        agent_id=event_in.agent_id,
        event_type=event_in.event_type,
        tool_name=event_in.tool_name,
        arguments=event_in.arguments,
        decision=outcome["decision"],
        policy_result=outcome["policy_result"],
        risk_score=outcome["risk_score"],
        risk_level=outcome["risk_level"],
        # A BLOCKed/REQUIRE_APPROVAL call never reaches the Tool Executor,
        # so it has no execution outcome to report later - mark it now
        # rather than leaving it stuck at PENDING forever.
        execution_status="PENDING" if outcome["decision"] == "ALLOW" else outcome["decision"],
    )
    db.add(event)

    if outcome["decision"] == "REQUIRE_APPROVAL":
        db.add(Approval(
            event_id=event_in.event_id,
            agent_id=event_in.agent_id,
            session_id=event_in.session_id,
            tool_name=event_in.tool_name,
            arguments=event_in.arguments,
            policy_result=outcome["policy_result"],
            risk_score=outcome["risk_score"],
            risk_level=outcome["risk_level"],
            reason=outcome["reason"],
            status="PENDING",
        ))

    db.commit()

    return DecisionOut(event_id=event.event_id, **outcome)


@router.post("/{event_id}/result")
def report_tool_result(event_id: str, result_in: ToolResultIn, db: Session = Depends(get_db)):
    event = db.execute(
        select(Event).where(Event.event_id == event_id)
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="event not found")

    event.execution_status = result_in.execution_status
    event.result = result_in.result
    event.error = result_in.error
    event.duration_ms = result_in.duration_ms
    db.commit()
    return {"ok": True}


@router.get("")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Event).order_by(Event.created_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "event_id": r.event_id,
            "session_id": r.session_id,
            "agent_id": r.agent_id,
            "tool_name": r.tool_name,
            "arguments": r.arguments,
            "decision": r.decision,
            "policy_result": r.policy_result,
            "risk_score": r.risk_score,
            "risk_level": r.risk_level,
            "execution_status": r.execution_status,
            "result": r.result,
            "error": r.error,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

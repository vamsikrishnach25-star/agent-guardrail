"""
Policies API.

Exists so policies are genuinely configurable (create/edit/disable) without
touching code or redeploying - Week 7's dashboard is just a UI on top of
this. Full edit-history/versioning is out of scope for Week 2; this is
plain CRUD for now.

Week 6: every route here requires a logged-in dashboard user - editing
policy is a meaningfully privileged action (it changes what the system
will ALLOW/BLOCK/REQUIRE_APPROVAL for every future call) and was
unauthenticated before this.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..database import get_db
from ..models import Policy, User
from ..schemas import PolicyIn, PolicyOut

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])

VALID_ACTIONS = {"ALLOW", "BLOCK", "REQUIRE_APPROVAL"}


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db), _user: User = Depends(require_user)):
    return db.execute(select(Policy).order_by(Policy.priority.asc())).scalars().all()


@router.post("", response_model=PolicyOut)
def create_policy(policy_in: PolicyIn, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    if policy_in.action not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"action must be one of {VALID_ACTIONS}")
    existing = db.execute(select(Policy).where(Policy.name == policy_in.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="a policy with this name already exists")
    policy = Policy(**policy_in.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: str, policy_in: PolicyIn, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="policy not found")
    for field, value in policy_in.model_dump().items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    policy = db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="policy not found")
    db.delete(policy)
    db.commit()
    return {"ok": True}

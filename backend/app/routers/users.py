"""
Week 11: user account management - create/list/change-role/delete,
entirely admin-only (`require_admin`). This is RBAC's actual provisioning
surface: an ADMIN account is what lets someone hand out APPROVER or
VIEWER accounts to the rest of a team without sharing the one admin
login, which is the whole point of adding roles in the first place.

Deliberately no self-registration - same philosophy routers/auth.py's
login endpoint already states about itself ("no registration/password-
reset flow... a real deployment would put this behind SSO anyway"): this
is an internal tool, accounts are provisioned by an admin, not signed up
for by anyone who finds the URL.

Two safety checks worth calling out (`_is_last_admin`): an admin can't
delete their own account, and can't delete or demote the *last* remaining
admin account (their own or anyone else's) - either one would either lock
the actor out immediately, or leave the whole system with no admin at all
and therefore no way to ever create one again short of a database edit.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import User, VALID_ROLES
from ..schemas import UserCreateIn, UserOut, UserRoleUpdateIn
from ..security import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _admin_count(db: Session) -> int:
    return len(db.execute(select(User.id).where(User.role == "ADMIN")).all())


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.execute(select(User).order_by(User.username.asc())).scalars().all()


@router.post("", response_model=UserOut)
def create_user(user_in: UserCreateIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if user_in.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    existing = db.execute(select(User).where(User.username == user_in.username)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="a user with this username already exists")
    user = User(username=user_in.username, password_hash=hash_password(user_in.password), role=user_in.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: str,
    payload: UserRoleUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user.role == "ADMIN" and payload.role != "ADMIN" and _admin_count(db) <= 1:
        raise HTTPException(status_code=409, detail="cannot demote the last remaining admin")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user_account(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot delete your own account")
    if user.role == "ADMIN" and _admin_count(db) <= 1:
        raise HTTPException(status_code=409, detail="cannot delete the last remaining admin")
    db.delete(user)
    db.commit()
    return {"ok": True}

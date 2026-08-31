"""
Week 6: dashboard login.

    POST /api/v1/auth/login  - username + password -> JWT
    GET  /api/v1/auth/me     - who am I, per the current session

Deliberately minimal: one login endpoint, no registration/password-reset
flow (out of scope for a portfolio project - a real deployment would put
this behind SSO anyway, not hand-rolled passwords). See seed_admin.py for
how the one bootstrap user gets created.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..database import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import JWT_EXPIRY_SECONDS, create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(login_in: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == login_in.username)).scalar_one_or_none()

    # Deliberately identical error for "no such user" and "wrong password" -
    # distinguishing them lets an attacker enumerate valid usernames.
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenOut(access_token=token, username=user.username, expires_in_seconds=JWT_EXPIRY_SECONDS)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(require_user)):
    return current_user

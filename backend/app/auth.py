"""
Week 6: FastAPI auth dependencies.

Two credential types, two dependencies - never mixed:

- `require_agent`   - validates an `X-API-Key` header against the api_keys
                       table. Used on the SDK-facing write paths (report a
                       tool call, report a result, poll approval status for
                       one's own event). Returns the ApiKey row so callers
                       can enforce "this key's agent_id must match the
                       event's agent_id".
- `require_user`    - validates an `Authorization: Bearer <jwt>` header.
                       Used on every dashboard-facing endpoint (list events,
                       manage policies, list/approve/deny approvals, manage
                       API keys). Returns the User row.

Both raise 401 with a clear reason rather than letting a downstream KeyError
or AttributeError surface - an auth layer that fails unpredictably is worse
than one that's simply strict.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import ApiKey, User
from .security import decode_access_token, hash_api_key


def require_agent(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing X-API-Key header")

    key_hash = hash_api_key(x_api_key)
    api_key = db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    ).scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="invalid API key")
    if api_key.revoked_at is not None:
        raise HTTPException(status_code=401, detail="this API key has been revoked")

    return api_key


def require_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="invalid or expired session")

    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="user no longer exists")

    return user

"""
Week 6: API key management for agents.

    POST   /api/v1/keys           - mint a new key for an agent_id (raw key
                                     shown once in the response, then never
                                     again)
    GET    /api/v1/keys           - list keys (preview only, no hashes/raw
                                     keys)
    POST   /api/v1/keys/{id}/revoke - revoke a key immediately

Gated by the same dashboard login as everything else here (`require_user`) -
there's deliberately no separate "admin" credential type. Minting an agent
credential is exactly the kind of action that should require a logged-in
human, same as approving a transfer.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..database import get_db
from ..models import ApiKey, User
from ..schemas import ApiKeyCreatedOut, ApiKeyIn, ApiKeyOut
from ..security import generate_api_key

router = APIRouter(prefix="/api/v1/keys", tags=["keys"])


def _preview(key_hash: str) -> str:
    return f"...{key_hash[-6:]}"


def _serialize(k: ApiKey) -> dict:
    return {
        "id": k.id,
        "agent_id": k.agent_id,
        "label": k.label,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
        "key_preview": _preview(k.key_hash),
    }


@router.get("", response_model=list[ApiKeyOut])
def list_keys(db: Session = Depends(get_db), _user: User = Depends(require_user)):
    rows = db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars().all()
    return [_serialize(k) for k in rows]


@router.post("", response_model=ApiKeyCreatedOut)
def create_key(key_in: ApiKeyIn, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    raw_key, key_hash = generate_api_key()
    key = ApiKey(agent_id=key_in.agent_id, label=key_in.label, key_hash=key_hash)
    db.add(key)
    db.commit()
    db.refresh(key)
    return {**_serialize(key), "raw_key": raw_key}


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_key(key_id: str, db: Session = Depends(get_db), _user: User = Depends(require_user)):
    key = db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(key)
    return _serialize(key)

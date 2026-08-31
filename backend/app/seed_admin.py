"""
Week 6: seeds exactly one admin user and one demo agent API key on first
startup - same "only if the table is empty" pattern as seed_policies.py, so
this preserves the project's zero-setup local dev story even though real
auth now exists.

Credentials come from env vars if set (GUARDRAIL_ADMIN_USERNAME /
GUARDRAIL_ADMIN_PASSWORD); otherwise a random password is generated and
printed to the console ONCE. Same idea for the demo API key: printed once,
because - same as the real thing - it's stored only as a hash after that
and cannot be recovered.
"""
import os
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKey, User
from .security import generate_api_key, hash_password


def seed_admin_user(db: Session) -> None:
    existing = db.execute(select(User.id).limit(1)).first()
    if existing:
        return

    username = os.environ.get("GUARDRAIL_ADMIN_USERNAME", "admin")
    password = os.environ.get("GUARDRAIL_ADMIN_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    db.add(User(username=username, password_hash=hash_password(password)))
    db.commit()

    print("=" * 72)
    print("[guardrail] Seeded the first dashboard login:")
    print(f"[guardrail]   username: {username}")
    if generated:
        print(f"[guardrail]   password: {password}  (generated - save this, it won't be shown again)")
    else:
        print("[guardrail]   password: <from GUARDRAIL_ADMIN_PASSWORD>")
    print("=" * 72)


def seed_demo_api_key(db: Session) -> None:
    existing = db.execute(select(ApiKey.id).limit(1)).first()
    if existing:
        return

    raw_key, key_hash = generate_api_key()
    db.add(ApiKey(agent_id="finance-agent", label="demo agent (seeded)", key_hash=key_hash))
    db.commit()

    print("=" * 72)
    print("[guardrail] Seeded a demo API key for agent_id='finance-agent':")
    print(f"[guardrail]   {raw_key}")
    print("[guardrail]   (only shown once - use this in demo_agent's Guardrail(api_key=...))")
    print("=" * 72)

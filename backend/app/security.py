"""
Week 6: cryptographic primitives for auth. Kept in one small module so the
"how are secrets actually handled" story is easy to point to in an
interview, rather than scattered across routers.

Two distinct credential types, deliberately different mechanisms:

- Human dashboard sessions -> JWT (stateless, short-lived, signed with
  GUARDRAIL_JWT_SECRET). Humans log in with a password; a JWT is the
  standard, simple way to avoid a server-side session table for something
  short-lived and low-consequence-if-stolen-briefly.
- Agent API keys -> opaque random tokens, stored as a SHA-256 hash (never
  the raw key) in the `api_keys` table, individually revocable. These are
  long-lived machine credentials with a much bigger blast radius if leaked
  (an agent's key can report tool calls on its behalf indefinitely), so
  they get a mechanism that supports revocation - a JWT can't be revoked
  without extra infrastructure (a denylist), which defeats the point of
  being stateless.

Passwords use bcrypt (via the `bcrypt` package directly, not passlib, to
avoid an extra abstraction layer / version-compat surface for a project
this size).
"""
import hashlib
import os
import secrets
import time

import bcrypt
import jwt

JWT_SECRET = os.environ.get("GUARDRAIL_JWT_SECRET", "dev-insecure-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 8  # 8 hours - long enough for a work session, short enough to matter

if JWT_SECRET == "dev-insecure-secret-change-in-production":
    print(
        "[guardrail][WARN] GUARDRAIL_JWT_SECRET not set - using an insecure default. "
        "Set this env var to a random value before deploying anywhere real."
    )


# ---- passwords ----

def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # malformed hash - treat as "does not match" rather than crashing
        return False


# ---- JWTs (human dashboard sessions) ----

def create_access_token(user_id: str, username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + JWT_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---- API keys (agent/SDK credentials) ----

def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, key_hash). Only the hash is stored - the raw key
    is shown to the caller exactly once, same pattern as GitHub PATs."""
    raw_key = f"gk_{secrets.token_urlsafe(32)}"
    return raw_key, hash_api_key(raw_key)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

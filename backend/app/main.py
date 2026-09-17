from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from .migrations import run_startup_migrations
from .routers import events, policies, approvals, auth, keys, users
from .seed_admin import seed_admin_user, seed_demo_api_key, seed_support_api_key
from .seed_policies import seed_default_policies, seed_support_policies

# Week 1: create tables directly for anything brand-new. Week 11 adds a
# small hand-rolled migration step before this, for the one case
# create_all() can't handle: a column added to a table that already has
# rows on the live deployment (see migrations.py for why this isn't
# Alembic).
run_startup_migrations(engine)
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_default_policies(db)
    seed_admin_user(db)
    seed_demo_api_key(db)
    # Week 10: both upsert-by-name/agent_id, so unlike the three calls
    # above they run (and do something useful) on every startup, not just
    # a brand-new install - see their docstrings for why that matters for
    # the already-live deployment.
    seed_support_policies(db)
    seed_support_api_key(db)

app = FastAPI(title="Agent Guardrail", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(events.router)
app.include_router(policies.router)
app.include_router(approvals.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}

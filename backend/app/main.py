from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from .routers import events, policies, approvals, auth, keys
from .seed_admin import seed_admin_user, seed_demo_api_key
from .seed_policies import seed_default_policies

# Week 1: create tables directly. Alembic migrations get introduced once
# the schema stabilizes past Week 2 (policies/risk/approvals tables).
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_default_policies(db)
    seed_admin_user(db)
    seed_demo_api_key(db)

app = FastAPI(title="Agent Guardrail", version="0.2.0")

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


@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from .routers import events, policies, approvals
from .seed_policies import seed_default_policies

# Week 1: create tables directly. Alembic migrations get introduced once
# the schema stabilizes past Week 2 (policies/risk/approvals tables).
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_default_policies(db)

app = FastAPI(title="Agent Guardrail", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(policies.router)
app.include_router(approvals.router)


@app.get("/health")
def health():
    return {"status": "ok"}

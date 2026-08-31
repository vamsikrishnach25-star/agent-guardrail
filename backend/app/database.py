"""
Database session setup.

Reads DATABASE_URL from the environment. Defaults to a local SQLite file
(guardrail_dev.db) so the project runs with zero setup on any machine -
no Postgres install, no Docker, no root access needed. In production, set
DATABASE_URL to a real hosted Postgres instance (Render/Railway/RDS/etc) -
no code changes needed, only the env var. SQLAlchemy + these models work
against both engines unchanged.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./guardrail_dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

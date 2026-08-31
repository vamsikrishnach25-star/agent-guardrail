"""
Local dev launcher. Starts the FastAPI backend against a local SQLite file
(guardrail_dev.db) by default - no database install needed on any OS.

To run against a real Postgres instead (e.g. testing before deployment),
set DATABASE_URL before running this script:

    Windows (PowerShell):  $env:DATABASE_URL="postgresql://user:pass@host/db"
    macOS/Linux:            export DATABASE_URL="postgresql://user:pass@host/db"

Usage:
    python scripts/start_dev.py
"""
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, app_dir=str(ROOT / "backend"))

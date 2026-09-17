"""
Week 11: verifies run_startup_migrations() actually does the thing it
exists for - adding `role` to a `users` table that predates that column
having existed, i.e. exactly the shape of the live Render deployment's
table before this migration runs there for the first time.

Uses its own throwaway sqlite file and a fresh engine, deliberately not
the shared app engine conftest.py's `db` fixture manages - the whole
point here is to start from a table shape the current SQLAlchemy models
would never produce on their own (no `role` column), which the app's
normal fixtures can't represent.
"""
import os
import tempfile
import uuid

from sqlalchemy import create_engine, inspect, text

from app.migrations import run_startup_migrations


def _old_style_engine():
    path = os.path.join(tempfile.gettempdir(), f"guardrail_migration_test_{uuid.uuid4().hex}.db")
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE users ("
            "id VARCHAR PRIMARY KEY, "
            "username VARCHAR UNIQUE NOT NULL, "
            "password_hash VARCHAR NOT NULL, "
            "created_at DATETIME NOT NULL"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO users (id, username, password_hash, created_at) "
            "VALUES ('u1', 'preexisting-admin', 'somehash', '2026-01-01 00:00:00')"
        ))
    return engine


def test_migration_adds_missing_role_column():
    engine = _old_style_engine()
    columns_before = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "role" not in columns_before

    run_startup_migrations(engine)

    columns_after = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "role" in columns_after


def test_migration_defaults_existing_users_to_admin():
    """Existing users had unrestricted access before RBAC existed - the
    migration must not silently downgrade them to VIEWER."""
    engine = _old_style_engine()
    run_startup_migrations(engine)

    with engine.connect() as conn:
        role = conn.execute(text("SELECT role FROM users WHERE id = 'u1'")).scalar_one()
    assert role == "ADMIN"


def test_migration_is_idempotent():
    """Running it twice (e.g. two backend instances starting up at once,
    or just a redeploy) must not error or duplicate anything."""
    engine = _old_style_engine()
    run_startup_migrations(engine)
    run_startup_migrations(engine)  # must not raise

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
    assert count == 1


def test_migration_does_nothing_to_a_table_that_already_has_the_column():
    engine = _old_style_engine()
    run_startup_migrations(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}

    run_startup_migrations(engine)  # second call: role already present, must be a no-op
    columns_again = {c["name"] for c in inspect(engine).get_columns("users")}
    assert columns == columns_again


def test_migration_skips_a_brand_new_database_with_no_users_table_yet():
    """A completely fresh database has no `users` table at all yet -
    create_all() (called right after this in main.py) handles that case
    correctly on its own. The migration must not error trying to inspect
    a table that doesn't exist."""
    path = os.path.join(tempfile.gettempdir(), f"guardrail_migration_test_{uuid.uuid4().hex}.db")
    engine = create_engine(f"sqlite:///{path}", future=True)
    run_startup_migrations(engine)  # must not raise
    assert "users" not in inspect(engine).get_table_names()

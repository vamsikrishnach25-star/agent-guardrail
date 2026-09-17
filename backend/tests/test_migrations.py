"""
Verifies run_startup_migrations() actually does the thing it exists for -
adding a missing column to a table that predates that column having
existed, i.e. exactly the shape of the live Render deployment's tables
before each migration ran there for the first time.

Uses its own throwaway sqlite file and a fresh engine per test,
deliberately not the shared app engine conftest.py's `db` fixture manages
- the whole point here is to start from table shapes the current
SQLAlchemy models would never produce on their own, which the app's
normal fixtures can't represent.

`test_reproduces_the_actual_production_failure` is the important one:
it's a regression test for a real bug that shipped in Week 9 and broke
every Render deploy from Week 10 onward (`condition_dsl` was added to the
Policy model with no migration for it) - it doesn't just check the column
exists, it does the exact INSERT that failed in production and asserts it
now succeeds.
"""
import os
import tempfile
import uuid

from sqlalchemy import create_engine, inspect, text

from app.migrations import run_startup_migrations


def _fresh_engine():
    path = os.path.join(tempfile.gettempdir(), f"guardrail_migration_test_{uuid.uuid4().hex}.db")
    return create_engine(f"sqlite:///{path}", future=True)


def _old_style_users_engine():
    """A `users` table shaped like it was before Week 11 - no `role`."""
    engine = _fresh_engine()
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


def _old_style_policies_engine():
    """A `policies` table shaped like it was before Week 9 - no
    `condition_dsl`. This is the exact shape the live deployment's table
    was actually in when Week 10's deploy failed."""
    engine = _fresh_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE policies ("
            "id VARCHAR PRIMARY KEY, name VARCHAR UNIQUE NOT NULL, tool_name VARCHAR NOT NULL, "
            "condition VARCHAR, action VARCHAR NOT NULL, priority INTEGER NOT NULL, "
            "enabled BOOLEAN NOT NULL, description VARCHAR, "
            "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL"
            ")"
        ))
    return engine


# ---- users.role ----

def test_migration_adds_missing_role_column():
    engine = _old_style_users_engine()
    assert "role" not in {c["name"] for c in inspect(engine).get_columns("users")}

    run_startup_migrations(engine)

    assert "role" in {c["name"] for c in inspect(engine).get_columns("users")}


def test_migration_defaults_existing_users_to_admin():
    """Existing users had unrestricted access before RBAC existed - the
    migration must not silently downgrade them to VIEWER."""
    engine = _old_style_users_engine()
    run_startup_migrations(engine)

    with engine.connect() as conn:
        role = conn.execute(text("SELECT role FROM users WHERE id = 'u1'")).scalar_one()
    assert role == "ADMIN"


# ---- policies.condition_dsl ----

def test_migration_adds_missing_condition_dsl_column():
    engine = _old_style_policies_engine()
    assert "condition_dsl" not in {c["name"] for c in inspect(engine).get_columns("policies")}

    run_startup_migrations(engine)

    assert "condition_dsl" in {c["name"] for c in inspect(engine).get_columns("policies")}


def test_reproduces_the_actual_production_failure():
    """Regression test: build the table shape the live deployment
    actually had (no condition_dsl), run the migration, then perform the
    exact kind of INSERT seed_support_policies() does - a policy row with
    a real condition_dsl value. Before this migration existed, this raised
    `sqlalchemy.exc.OperationalError: no such column: condition_dsl`
    (sqlite) / `UndefinedColumn` (the Postgres error actually seen on
    Render) and took the whole deploy down with it."""
    engine = _old_style_policies_engine()
    run_startup_migrations(engine)

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO policies "
            "(id, name, tool_name, condition, condition_dsl, action, priority, enabled, description, created_at, updated_at) "
            "VALUES (:id, :name, :tool_name, :condition, :condition_dsl, :action, :priority, :enabled, :description, :created_at, :updated_at)"
        ), {
            "id": "p1", "name": "fraudulent-refund-block", "tool_name": "issue_refund",
            "condition": None, "condition_dsl": '{"field": "arguments.amount", "op": "gt", "value": 20000}',
            "action": "BLOCK", "priority": 5, "enabled": True, "description": "test",
            "created_at": "2026-01-01 00:00:00", "updated_at": "2026-01-01 00:00:00",
        })  # must not raise

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM policies")).scalar_one()
    assert count == 1


# ---- both columns together, general properties ----

def test_migration_is_idempotent():
    """Running it twice (e.g. two backend instances starting up at once,
    or just a redeploy) must not error or duplicate anything."""
    engine = _old_style_users_engine()
    run_startup_migrations(engine)
    run_startup_migrations(engine)  # must not raise

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
    assert count == 1


def test_migration_does_nothing_to_a_table_that_already_has_the_column():
    engine = _old_style_users_engine()
    run_startup_migrations(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}

    run_startup_migrations(engine)  # second call: role already present, must be a no-op
    columns_again = {c["name"] for c in inspect(engine).get_columns("users")}
    assert columns == columns_again


def test_migration_skips_tables_that_do_not_exist_yet():
    """A completely fresh database has neither table yet - create_all()
    (called right after this, in main.py) handles that case correctly on
    its own. The migration must not error trying to inspect a table that
    doesn't exist."""
    engine = _fresh_engine()
    run_startup_migrations(engine)  # must not raise
    assert inspect(engine).get_table_names() == []

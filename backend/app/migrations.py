"""
A tiny, hand-rolled startup migration - not Alembic.

Two columns added to already-existing, already-live tables so far:

- `users.role` (Week 11) - RBAC.
- `policies.condition_dsl` (Week 9) - the structured policy DSL. This one
  was a real bug, not a hypothetical: it was added to the model back in
  Week 9 with no migration for it, and went unnoticed because nothing at
  startup wrote to that column on the live deployment until Week 10's
  seed_support_policies() started inserting rows with it - at which point
  every deploy from Week 10 onward failed with `column "condition_dsl"
  of relation "policies" does not exist`. Fixed here, alongside making
  this file handle more than one column so the same mistake is harder to
  repeat: `_ensure_column()` is the general form, `run_startup_migrations`
  is just a short list of calls to it.

`Base.metadata.create_all()` (used since Week 1, see database.py/main.py)
only creates tables that don't exist yet - it never alters an existing
one. Any column added to a model after a table has already been created
somewhere with real data in it needs an explicit entry here, or it will
silently work in fresh/local SQLite (create_all() makes the column
correctly from the start there) while quietly breaking the next write to
that column on the live deployment - exactly what happened above.

The proportionate fix at this project's scale is a single idempotent "add
the column if it's missing" check per column, run before create_all().
Alembic is the right tool once there's a real migration history with more
changes to track - the codebase's own database.py docstring has flagged
that as coming "once the schema stabilizes" since Week 1 - but reaching
for a full migration framework here would be a bigger dependency than two
columns justify. Being able to explain that trade-off, and to say plainly
when it stops being true, matters more than reflexively using the
"proper" tool - though the Week 9 miss above is itself the honest
counter-argument: a real migration tool would have made this class of bug
structurally harder to make in the first place, by forcing every schema
change through one reviewed, ordered migration file instead of relying on
someone remembering to update this one by hand each time.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _ensure_column(engine: Engine, table: str, column: str, ddl_type: str) -> None:
    """Adds `column` to `table` if it's missing, doing nothing if the
    table doesn't exist yet (a brand-new database - create_all(), called
    right after this in main.py, creates it with every column already
    correct) or already has the column (already migrated, or a fresh
    install that never needed migrating)."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    if column in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
    print(f"[guardrail] migrated: added {table}.{column}")


def run_startup_migrations(engine: Engine) -> None:
    # Existing users default to ADMIN, not VIEWER - this preserves exactly
    # the access they already had (everyone was effectively unrestricted
    # before RBAC existed), so a live deployment's existing admin doesn't
    # get silently locked out of anything the moment this migration runs.
    _ensure_column(engine, "users", "role", "VARCHAR NOT NULL DEFAULT 'ADMIN'")

    # Nullable, no default needed - a NULL condition_dsl on an existing
    # policy just means "this policy doesn't use the DSL", which is
    # already exactly what the code treats it as everywhere else
    # (policy_engine.py falls back to the legacy `condition` string).
    _ensure_column(engine, "policies", "condition_dsl", "JSON")

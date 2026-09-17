"""
Week 11: a tiny, hand-rolled startup migration - not Alembic.

Adding `User.role` (see models.py) is the first time this project has
needed to change the shape of a table that's already live with real rows
in it - the Render deployment's `users` table already has the seeded
admin account, and possibly more. `Base.metadata.create_all()` (used
since Week 1, see database.py/main.py) only creates tables that don't
exist yet - it never alters an existing one, so on its own it would leave
the deployed `users` table without a `role` column, and every login/`/me`
query would start raising `column users.role does not exist` the moment
this code deploys. That's not a hypothetical: it's exactly what would
happen on the next Render deploy without this file.

The proportionate fix for one new column, on one table, at this project's
scale, is a single idempotent "add the column if it's missing" check run
before create_all(). Alembic is the right tool once there's a real
migration history with more than one change to manage - the codebase's
own database.py docstring has flagged that as coming "once the schema
stabilizes" since Week 1 - but reaching for a full migration framework
here, for a single column, would be a bigger dependency than the problem
justifies. Being able to explain that trade-off (and to say plainly when
it would stop being true - the next schema change is probably where
Alembic actually becomes worth it) matters more than reflexively reaching
for the "proper" tool.

Existing users default to role='ADMIN' on migration, not 'VIEWER' - this
preserves exactly the access level they already had (everyone was
effectively unrestricted before RBAC existed), so a live deployment's
existing admin doesn't get silently locked out of anything the moment
this migration runs.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_startup_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        # Brand-new database - create_all() (called right after this, in
        # main.py) will create `users` with every column already correct.
        # Nothing to migrate.
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    if "role" in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'ADMIN'"))
    print("[guardrail] migrated: added users.role column (existing users default to ADMIN)")

# Agent Guardrail

[![CI](https://github.com/vamsikrishnach25-star/agent-guardrail/actions/workflows/ci.yml/badge.svg)](https://github.com/vamsikrishnach25-star/agent-guardrail/actions/workflows/ci.yml)

Runtime safety and observability platform for AI agents. Sits between an
agent and the tools/APIs it's allowed to call: intercepts tool calls,
evaluates policy and risk, allows/blocks/pauses for human approval, and
logs a complete audit trail.

**Live demo:** dashboard at https://agent-guardrail-1-olau.onrender.com,
backend API at https://agent-guardrail-zuls.onrender.com — both on
Render's free tier, so the first request after idle time can take 30-50s
to wake up. Sign in with the dashboard's seeded admin login (see
`DEPLOYMENT.md` for how to check the deployed backend's logs for it), then
run `demo_agent/test_deployed.py` with a matching API key to generate live
activity against the deployed backend.

Full architecture and phased plan: see `Agent_Guardrail_Build_Plan.md` and
`Agent_Guardrail_Project_Proposal.docx` in this folder.

## Status: Week 11 — RBAC: Admin / Approver / Viewer roles

Everything from Weeks 1-10, plus real role-based access control on top of
the JWT login that's existed since Week 6 - one flat admin account
replaced with three roles, each genuinely restricted server-side, not
just hidden in the UI.

- **Three roles.** VIEWER: read-only everywhere (events, approvals,
  policies, keys). APPROVER: VIEWER + can approve/deny. ADMIN: APPROVER +
  can manage policies, API keys, and other users' accounts. Enforced by
  `require_role()`/`require_admin`/`require_approver` (`auth.py`) wrapping
  the existing `require_user` - every dashboard route still needs a valid
  session first; role only narrows what a valid session can do.
- **`POST/GET /api/v1/users`, `PATCH /{id}/role`, `DELETE /{id}`** -
  admin-only account management (`routers/users.py`). No self-
  registration, same as login itself - accounts are provisioned by an
  admin. Two safety checks: you can't delete your own account, and you
  can't delete or demote the *last* remaining admin (either would risk
  locking the whole system out of ever having an admin again).
- **A real schema migration on an already-live database.** Adding
  `User.role` is the first time this project has changed the shape of a
  table that already has rows in it on the live Render deployment -
  `Base.metadata.create_all()` (used since Week 1) only creates tables
  that don't exist yet, it never alters an existing one. `migrations.py`
  is a small, hand-rolled, idempotent "add the column if it's missing"
  check that runs before `create_all()`; existing users default to ADMIN
  on migration, preserving exactly the access they already had rather
  than silently downgrading them. Verified in a sandbox against a sqlite
  file built to look exactly like the pre-migration live database
  (old-shape `users` table, one existing row, no `role` column) before
  ever touching the real deployment.
- **Role-aware dashboard UI**, but the UI hiding a button was never the
  actual security boundary - the backend enforces every restriction
  independently regardless of what the frontend shows. A new **Users**
  tab (ADMIN-only) to create accounts, change roles, and remove users;
  Approve/Deny, policy create/edit/delete, and API key mint/revoke all
  hide for roles that can't use them.
- **34 new backend tests** (131 total): the full ADMIN/APPROVER/VIEWER
  permission matrix across every router, the user-management safety
  checks, and - separately - the migration itself, exercised against a
  hand-built pre-RBAC-shaped table the same way the sandbox smoke test
  was, so the riskiest part of this week has direct test coverage, not
  just a one-off manual check.

Previous weeks: a second demo agent proving Guardrail isn't finance-only
(Week 10), a structured policy DSL with `all`/`any`/`not` combinators and
a dry-run `/policies/simulate` endpoint (Week 9), a real GPT
function-calling agent through the same SDK (Week 8), a pytest suite with
CI on every push/PR (Week 7), API key auth for agents and real JWT
dashboard login (Week 6), Docker (`docker-compose up --build`), measured
benchmarks (`BENCHMARKS.md`), and a live deployment (`DEPLOYMENT.md`).

That's every item from the original build plan's stretch layer except
anomaly detection and the (purely cosmetic) execution graph - see
`Agent_Guardrail_Build_Plan.md` for what's left if there's still runway
before interviews.

## Project layout

```
agent-guardrail/
  .github/workflows/ci.yml Runs the backend test suite on every push/PR
  backend/
    Dockerfile             Backend container (see comment re: build context)
    pytest.ini              Points pytest at backend/tests
    conftest.py              Shared fixtures: test DB reset+reseed, auth/agent headers
    tests/                   131 tests: auth, RBAC, migrations, events/policy pipeline, approvals, policies, keys, DSL
    app/
      policy_engine.py      Evaluates configured policies against a tool call
      policy_dsl.py            Week 9: structured condition tree (AST + evaluator)
      pipeline.py               Week 9: shared policy->risk->decision pipeline (events + simulate)
      risk_engine.py         Additive risk scoring (0-100 -> LOW/MEDIUM/HIGH/CRITICAL)
      decision_engine.py     Combines policy + risk into one final decision
      security.py             Password hashing (bcrypt), API key gen, JWT encode/decode
      auth.py                  FastAPI deps: require_agent/require_user + (Week 11) require_admin/require_approver
      migrations.py             Week 11: tiny hand-rolled startup migration (adds users.role safely)
      seed_policies.py       Seeds default + (Week 10) support-agent policies
      seed_admin.py            Seeds admin login (role=ADMIN) + demo API keys (finance + support agents)
      routers/events.py      POST tool call -> decision (API key); GET events (login)
      routers/policies.py    CRUD (ADMIN) + /simulate dry-run (any role) for policies
      routers/approvals.py   List (any role) + approve/deny (APPROVER/ADMIN) + by-event poll (API key)
      routers/auth.py          POST /auth/login -> JWT; GET /auth/me (includes role)
      routers/keys.py          List (any role); mint/revoke (ADMIN)
      routers/users.py          Week 11: create/list/change-role/delete users (ADMIN only)
  sdk/guardrail_sdk/      The Guardrail SDK agents import to call tools through
  demo_agent/             Toy finance agent + tools used to exercise the system
    finance_agent.py        Week 1: hardcoded call sequence, proves the interception path
    openai_agent.py          Week 8: real GPT function-calling agent, same SDK/backend
    test_openai_agent.py    Mocked tests for the tool-calling <-> Guardrail wiring
  support_agent/          Week 10: second demo agent, a different domain (customer support)
    tools.py                 issue_refund, close_ticket, escalate_to_manager
    support_agent.py          Hardcoded call sequence, same SDK class as finance_agent.py
  frontend/               Vite + React dashboard (Overview, Approvals, Traces, Policies)
    Dockerfile             Multi-stage: Vite build -> nginx static serve
  scripts/start_dev.py    Local dev launcher (backend, SQLite by default)
  scripts/approve_cli.py  Terminal stand-in for the dashboard (still works, now optional)
  scripts/benchmark.py    Load-testing script - real latency/throughput numbers
  docker-compose.yml      One-command demo: backend + Postgres + frontend
  BENCHMARKS.md           Measured results + methodology (not estimates)
  DEPLOYMENT.md           Step-by-step guide to a live URL
```

## Running it locally

Requires Python 3.10+ and Node.js 18+. Use three terminals.

```bash
pip install -r requirements.txt

# terminal 1: FastAPI backend (SQLite by default)
python scripts/start_dev.py
```

On first startup the backend seeds an admin login and a demo API key for
each demo agent (finance + support, Week 10), printing each to the
console **once** (only a hash is stored after that - same as it would be
for a real deployment):

```
[guardrail] Seeded the first dashboard login:
[guardrail]   username: admin
[guardrail]   role: ADMIN
[guardrail]   password: <random>
...
[guardrail] Seeded a demo API key for agent_id='finance-agent':
[guardrail]   gk_...
...
[guardrail] Seeded a demo API key for agent_id='support-agent':
[guardrail]   gk_...
```

Save all three - the dashboard login is how you sign into the UI below,
and each API key is what that demo agent needs to authenticate. The
seeded account is ADMIN, so once you're in, the **Users** tab lets you
create APPROVER/VIEWER accounts to try out RBAC (Week 11) - log in as one
in a second browser/incognito window and watch the Approve/Deny buttons
and edit controls disappear for VIEWER, or stay for APPROVER but the
Policies/Keys/Users edit controls still don't.

```bash
# terminal 2: the dashboard
cd frontend
npm install
npm run dev
# open http://localhost:5173 and sign in with the seeded admin credentials
```

With the dashboard open, generate some activity:

```bash
# terminal 3
cd demo_agent
# Windows PowerShell:
$env:PYTHONPATH="..\sdk"
$env:GUARDRAIL_API_KEY="gk_..."   # the demo key from terminal 1's output
python finance_agent.py
# macOS/Linux:
PYTHONPATH=../sdk GUARDRAIL_API_KEY="gk_..." python3 finance_agent.py
```

`get_balance` shows up immediately in Overview/Trace Viewer. `transfer_money`
pauses the agent - switch to the dashboard's Approval Queue tab (it's
already polling, no refresh needed), approve or deny it there, and watch
terminal 3 unblock within a couple seconds. `delete_user` shows up as
BLOCKed with no approval step, since that policy blocks outright.

Need a key for a different agent_id, or want to revoke one? The dashboard's
**API Keys** tab does both, once you're logged in.

Check the raw API directly any time:

```bash
curl http://localhost:8000/api/v1/events
curl http://localhost:8000/api/v1/approvals
```

## Running the GPT-driven agent (Week 8)

With the backend and dashboard already running (see above), mint a
Guardrail API key for the new agent from the dashboard's **API Keys**
tab: agent_id `openai-finance-agent`. You'll also need an OpenAI API key
from platform.openai.com - this demo makes a handful of short
`gpt-4o-mini` calls, well under a dollar total.

```bash
# terminal 3 (instead of, or in addition to, finance_agent.py)
cd demo_agent
# PowerShell:
$env:PYTHONPATH="..\sdk"
$env:GUARDRAIL_API_KEY="gk_..."     # the key you just minted for openai-finance-agent
$env:OPENAI_API_KEY="sk-..."
python openai_agent.py
```

With no arguments it runs a default instruction that naturally exercises
all three outcomes - an allowed balance check, a high-value transfer that
needs approval, and a blocked user deletion - because GPT itself reads the
instruction and decides to call all three tools, not because the script
tells it to. Pass your own instruction instead:

```bash
python openai_agent.py "Check the balance on ACC1234 and transfer 500 to it"
```

Run the mocked tests (no API keys needed) any time with:

```bash
cd demo_agent
PYTHONPATH=../sdk pytest test_openai_agent.py -v
```

## Running the support agent (Week 10)

The second demo agent - proves the same SDK/backend works for a
completely different domain, not just finance. Its API key and policies
are seeded automatically alongside the finance agent's (see above), so
there's nothing extra to set up.

```bash
# terminal 3 (instead of, or in addition to, the others)
cd support_agent
# PowerShell:
$env:PYTHONPATH="..\sdk"
$env:GUARDRAIL_API_KEY="gk_..."   # the seeded support-agent key from terminal 1's output
python support_agent.py
```

Walks through all three outcomes again, in a different domain: escalating
a ticket is allowed outright (no policy targets it), a mid-size refund
pauses for approval, and a refund over 20,000 is blocked as likely fraud -
approve the pending one from the dashboard's Approval Queue the same way
you would for the finance agent, and watch terminal 3 unblock.

## Running the tests

```bash
pip install -r requirements.txt
cd backend
pytest -v
```

All 131 tests run against a throwaway SQLite file (`conftest.py` points
`DATABASE_URL` at one before anything else imports), reset to a clean,
identically-seeded schema before every test - no shared state between
tests, no dependency on execution order, no need for a real Postgres
instance just to run the suite. The same command runs in CI on every push
and pull request (`.github/workflows/ci.yml`).

### Why SQLite for local dev?

Local dev uses a SQLite file (`guardrail_dev.db`, created automatically) so
the project runs with zero setup on any machine — no Postgres install, no
Docker, no admin/root access needed. The code talks to the database only
through SQLAlchemy, so nothing in `backend/app` is SQLite-specific. For
deployment, set the `DATABASE_URL` env var to a real hosted Postgres
instance (Render/Railway/RDS/etc) — no code changes required.

## Running it with Docker

Requires Docker Desktop. This runs the real stack — Postgres instead of
the SQLite dev fallback — in one command:

```bash
docker-compose up --build
```

Backend: http://localhost:8000. Dashboard: http://localhost:5173. Data
persists in a Docker volume across restarts (`docker-compose down -v` to
wipe it). Generate activity the same way as local dev — run the demo
agent against `http://localhost:8000`.

## Benchmarks

`scripts/benchmark.py` load-tests the decision pipeline and reports real
latency percentiles, throughput, and decision breakdown — see
`BENCHMARKS.md` for methodology, actual measured results, and a genuine
finding (a SQLite write-lock bottleneck under concurrency) worth being
able to explain in an interview.

```bash
python scripts/benchmark.py --requests 500 --concurrency 20
```

## Deploying it

See `DEPLOYMENT.md` for step-by-step instructions to get this running on
a public URL (Render, or any Docker-based host) instead of just localhost.

## Design notes worth remembering for interviews

- **Fail-closed by default.** If the SDK can't reach the backend, it blocks
  the tool call rather than letting it through (see `sdk/guardrail_sdk/interceptor.py`).
  A safety system that fails open when it can't check defeats its own purpose.
- **The SDK is the enforcement boundary.** Tools are never called directly
  by agent code — everything goes through `session.call(tool_fn, **kwargs)`,
  which is what makes interception/policy/risk/approval possible at all.
- **Decision logic is isolated in one function** (`decide()` in
  `backend/app/routers/events.py`), which is why Week 2 could swap in the
  real Policy/Risk/Decision Engine pipeline without touching the API
  contract or the SDK at all.
- **Policy Engine and Risk Engine are deliberately separate systems.**
  Policy asks "does this violate a configured rule?" (yes/no). Risk asks
  "how dangerous is this?" (a score). `transfer_money(25000)` gets flagged
  by the high-value-transfer *policy* even though its *risk score* is only
  MEDIUM (50/100) — the two systems don't always agree, and the Decision
  Engine is what reconciles them (`decision_engine.py`).
- **Policy conditions are evaluated with `simpleeval`, not Python's
  `eval()`.** Policies are user-editable strings stored in the database;
  running them through real `eval()` would mean anyone who can write a
  policy can run arbitrary code inside the system whose entire job is
  stopping unauthorized actions. `simpleeval` only allows arithmetic/
  comparison expressions against the arguments dict — nothing else.
- **Risk-based safety net.** Even with zero matching policies, the Decision
  Engine still escalates to REQUIRE_APPROVAL if the Risk Engine scores an
  action HIGH or CRITICAL (`decision_engine.py`). Policies are written in
  advance by humans and will always lag behind reality; risk scoring is
  the catch-all for actions nobody's thought to write a rule for yet.
- **The approval queue is a DB table, not Redis - a deliberate trade-off,
  not an oversight.** The original design calls for Redis. At this
  project's scale, a polled table on the same database gives identical
  behavior with one less service to install and run, and it's a schema I
  can point to and say exactly how I'd move it to Redis (or switch polling
  for Postgres LISTEN/NOTIFY) if this needed to handle multiple backend
  instances or push-based updates. Be ready to explain this, not defend it
  as "the real thing" - it isn't, and pretending otherwise is worse than
  just owning the trade-off.
- **The SDK genuinely blocks while waiting for approval** (`_wait_for_approval`
  in `interceptor.py`) rather than faking a pause - `session.call()` really
  does not return until a human has acted or the poll times out. Real
  agent frameworks would want this as an async/await instead of a blocking
  poll loop so other work can continue, but the semantics (agent cannot
  proceed without a decision) are the same either way.
- **The dashboard needed zero new backend endpoints.** Every screen is
  built entirely on the events/approvals/policies API that already existed
  from Weeks 1-3 - proof that the API was designed around what the system
  needs to expose, not around what one specific client (the SDK) needed to
  call. Trace Viewer, for instance, just groups the same flat event list
  by `session_id` client-side; there's no separate "traces" endpoint.
- **Polling over WebSockets, deliberately.** Every screen refreshes every
  2.5-5s via plain `fetch`. For a handful of admins looking at a dashboard,
  that's indistinguishable from push in practice and is far simpler to
  build/debug than a WebSocket/SSE channel - the kind of complexity that's
  worth adding only once you actually need it (many concurrent viewers,
  sub-second latency requirements), not by default.
- **The benchmark found a real bottleneck, not just a throughput number.**
  Under concurrency 20 vs. concurrency 5, throughput stayed flat (~135-150
  req/s) while p99 latency roughly quadrupled (243ms -> 1083ms) - the
  signature of requests queuing behind a serialized resource rather than
  the code getting slower. SQLite allows one writer at a time, and every
  decision does a DB write, so that's the prime suspect (see
  `BENCHMARKS.md`). Diagnosing *why* a number is what it is, not just
  reporting it, is the difference between having run a benchmark and
  having understood one - the second is what interviewers are actually
  checking for when they ask about it.
- **Two credential types, deliberately different mechanisms (Week 6).**
  Dashboard sessions use a stateless JWT (`security.py`) - short-lived,
  cheap, fine to lose a few hours of validity if something goes wrong.
  Agent API keys use an opaque random token stored only as a SHA-256 hash,
  individually revocable (`routers/keys.py`). A JWT can't be revoked
  without extra infrastructure (a denylist), which is fine for a login
  session but wrong for a long-lived machine credential that might leak
  and needs to be killed immediately. Using the same mechanism for both
  would have been simpler to write and wrong to explain in an interview.
- **`decided_by` moved from the request body to the session (Week 6).**
  Through Week 5, anyone could POST `{"decided_by": "anyone"}` to the
  approve endpoint - the audit trail trusted whatever string the caller
  sent. It's now derived server-side from the authenticated JWT
  (`routers/approvals.py`), so the field genuinely means what it says.
  This is the kind of gap that's easy to miss in a first pass because the
  demo *works* either way - it only shows up when you ask "what stops
  someone from lying to the audit log," which is exactly the question an
  interviewer reviewing a safety tool is likely to ask.
- **Tests hit the real HTTP layer, not the engines directly (Week 7).**
  `backend/tests/` goes through FastAPI's `TestClient` for every test -
  login, then a real `POST /api/v1/events` with an API key header - rather
  than importing `decide()` and calling it as a plain function. That's
  deliberately more end-to-end: it also exercises auth, serialization, and
  persistence, so a bug in "the JWT dependency silently lets an expired
  token through" would actually get caught, whereas a pure unit test of
  the decision engine never touches that code path at all.
- **Every test starts from an identical, freshly-seeded database, not a
  shared one.** `conftest.py`'s `db` fixture drops and recreates the whole
  schema before each test, then reseeds one known admin user and the two
  default policies. The alternative - one shared test DB, tests hoping
  they don't interfere with each other - is exactly how test suites become
  order-dependent and flaky. It costs a bit of speed (each test pays for a
  schema rebuild); at 45 tests that trade is still worth it for suite
  reliability.
- **The LLM never touches a real function - only JSON (Week 8).** GPT
  picks a tool name and a JSON arguments blob; `openai_agent.py` looks
  that name up in a fixed `TOOL_FUNCTIONS` dict and calls the real Python
  function through `session.call()`. The model cannot invoke arbitrary
  code or call anything outside that dict, no matter what it "decides" -
  the same boundary that stops a compromised or hallucinating agent from
  doing something ungoverned is what stops a malicious prompt injection
  from doing the same thing. That boundary is also why a BLOCKed call
  comes back to the model as a normal-looking tool result (`{"error":
  "blocked by guardrail: ..."}`) instead of an exception crashing the
  loop - the model needs to see the outcome to explain it to the user,
  same as it would see any other tool failure.
- **Guardrail doesn't know or care that an LLM is involved at all.**
  Nothing in `backend/` or `sdk/` changed to support Week 8 - the whole
  integration is one new file that calls the exact same `session.call()`
  every other caller uses. That's the real test of "is the SDK actually
  the enforcement boundary, or just the boundary for the one caller we
  built it against" - and it held.
- **A structured tree instead of a bigger string grammar (Week 9).** The
  tempting shortcut was extending simpleeval's allowed syntax (add `and`/
  `or` support, more functions, etc). That just grows the surface area of
  a string being parsed as code. A JSON tree with a fixed set of node
  types (`all`/`any`/`not`/leaf) can express the same boolean logic
  without ever being "a string that might contain something clever" -
  every node is either a known combinator or a `{field, op, value}`
  triple, full stop. That's closer to how OPA/Rego structure rules
  (composable, structured, not a single opaque expression) without
  pulling in an actual policy-as-code runtime for a project this size.
- **The DSL and the legacy string are two paths through one function, not
  a rewrite.** `policy_engine.evaluate_policies()` checks `condition_dsl`
  first and falls back to `condition` - it was never "migrate everything
  or nothing." Real systems basically never get to do a clean-slate
  rewrite of something already in production; being asked "how would you
  roll out a new policy format without breaking every existing policy"
  is a fair interview question, and this is a genuine (if small-scale)
  answer to it, not a hypothetical one.
- **Validation happens at write time, evaluation fails safe at read
  time - deliberately different failure modes for different moments.**
  Saving a malformed `condition_dsl` gets a 400 immediately
  (`policy_dsl.validate()`, called from `routers/policies.py`) - the
  admin finds out right away. A comparison that fails *during* evaluation
  (wrong type, missing field) returns non-match instead of raising
  (`policy_dsl.evaluate()`) - one bad policy must never take down the
  decision pipeline for every other call in flight. Same two-failure-mode
  split the legacy simpleeval path already used; the DSL just makes it
  explicit instead of implicit.
- **The simulate endpoint reuses the real pipeline, not a copy of it.**
  `pipeline.py` was factored out specifically so `POST
  /api/v1/policies/simulate` and `POST /api/v1/events` call the exact
  same `run_pipeline()` - a "test mode" that quietly runs slightly
  different logic than production is worse than no test mode, because it
  can pass while the real path is broken (or vice versa).
- **The second demo agent is the actual proof, not the auth/tests/DSL
  weeks (Week 10).** Weeks 6-9 all made the *existing* finance agent
  more solid; none of them tested whether the system generalizes. Adding
  `support_agent/` - a different domain, different tools, different
  policies - with zero changes to `backend/` or `sdk/` is what actually
  answers "is this reusable infrastructure or a demo built around one
  agent's shape." It's a cheap way to expose a coupling bug if one
  exists (e.g. a policy field name the finance domain happened to always
  provide that the engine silently assumed), and here it didn't find
  one - which is itself the result worth being able to state plainly in
  an interview, not just claim.
- **Two different seeding strategies, on purpose, not by accident (Week
  10).** `seed_default_policies`/`seed_demo_api_key` (Weeks 1 & 6) check
  "is the whole table empty" - correct for a one-time bootstrap on a
  brand-new database, wrong for adding something new to a database
  that's already been running in production for weeks. `seed_support_
  policies`/`seed_support_api_key` check "does this specific named thing
  already exist" instead - safe to call unconditionally on every single
  startup, forever, because it's naturally idempotent per item rather
  than gated by a one-time table-level check. Knowing which of the two
  patterns a given migration/seed needs - and that they're not
  interchangeable - is a real production concern, not a toy-project one.
- **Authorization is a wrapper around authentication, not a rewrite of it
  (Week 11).** `require_role()` calls `require_user` as its own
  dependency and only adds a check on top - it doesn't reimplement
  "is this JWT valid." Every route that used to require *a* login now
  requires *the right kind of* login, but the actual session-validation
  code path is exactly the one thing Week 6 already built and this week
  didn't touch. Layering new authorization on unchanged authentication,
  instead of rewriting both together, is what kept this a same-day
  change instead of a multi-day one.
- **403, not 401, for a valid session with the wrong role.** 401 means
  "who are you" - your credentials didn't establish who's asking. 403
  means "I know who you are, and the answer is no." A VIEWER hitting
  `POST /policies` has a perfectly valid session; the problem is
  entirely about what that session is allowed to do. Conflating the two
  (or, worse, always returning 401) would make a client's own retry/
  refresh logic do the wrong thing - re-authenticating a VIEWER doesn't
  turn them into an ADMIN.
- **The riskiest line of code this week has the most direct test
  coverage, not the most incidental.** `migrations.py` is nine lines,
  but it's the one thing that could have taken the live deployment down
  on the next push - a wrong migration is a 500 on every single request,
  not a missing feature. It's the one module this week with tests built
  around a hand-constructed "what does the live database actually look
  like right now" fixture, plus a standalone sandbox run against that
  same shape, before ever touching the real thing. Test effort should
  track blast radius, not lines of code or how interesting a module was
  to write.

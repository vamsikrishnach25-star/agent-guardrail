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

## Status: Week 8 — a real LLM decides the tool calls, not a script

Everything from Weeks 1-7, plus proof Guardrail works on an agent that
actually thinks, not just a fixed sequence of function calls:

- **`demo_agent/openai_agent.py`** - a GPT-driven agent using OpenAI's
  function-calling API. Given a plain-English instruction, the model
  itself decides which tool(s) to call, in what order, and with what
  arguments - every one of those model-chosen calls still goes through
  `session.call()`, so the exact same policy/risk/approval pipeline
  applies to LLM-originated calls as to the toy `finance_agent.py`'s
  hardcoded ones. Swapping the decision-maker required zero changes to
  the SDK or backend - only this one new file.
- **6 tests for the tool-calling loop** (`demo_agent/test_openai_agent.py`)
  that mock the OpenAI response and the Guardrail session, so the
  translation logic (tool_call -> `session.call()` -> JSON result fed
  back to the model, including how a BLOCK gets surfaced instead of
  crashing the loop) is verified without spending real API calls.

Previous weeks: a 45-test pytest suite with CI on every push/PR (Week 7),
API key auth for agents and real JWT dashboard login (Week 6), Docker
(`docker-compose up --build`), measured benchmarks (`BENCHMARKS.md`), and
a live deployment (`DEPLOYMENT.md`).

A proper policy DSL (beyond simpleeval condition strings) is next - see
`Agent_Guardrail_Build_Plan.md` for the priority order if there's runway
left before interviews.

## Project layout

```
agent-guardrail/
  .github/workflows/ci.yml Runs the backend test suite on every push/PR
  backend/
    Dockerfile             Backend container (see comment re: build context)
    pytest.ini              Points pytest at backend/tests
    conftest.py              Shared fixtures: test DB reset+reseed, auth/agent headers
    tests/                   45 tests: auth, events/policy pipeline, approvals, policies, keys
    app/
      policy_engine.py      Evaluates configured policies against a tool call
      risk_engine.py         Additive risk scoring (0-100 -> LOW/MEDIUM/HIGH/CRITICAL)
      decision_engine.py     Combines policy + risk into one final decision
      security.py             Password hashing (bcrypt), API key gen, JWT encode/decode
      auth.py                  FastAPI dependencies: require_agent (API key), require_user (JWT)
      seed_policies.py       Seeds 2 default policies on first run
      seed_admin.py            Seeds 1 admin login + 1 demo API key on first run
      routers/events.py      POST tool call -> decision (API key); GET events (login)
      routers/policies.py    CRUD API for policies (all routes require login)
      routers/approvals.py   List/approve/deny (login) + by-event poll (API key)
      routers/auth.py          POST /auth/login -> JWT; GET /auth/me
      routers/keys.py          Mint/list/revoke agent API keys (requires login)
  sdk/guardrail_sdk/      The Guardrail SDK agents import to call tools through
  demo_agent/             Toy finance agent + tools used to exercise the system
    finance_agent.py        Week 1: hardcoded call sequence, proves the interception path
    openai_agent.py          Week 8: real GPT function-calling agent, same SDK/backend
    test_openai_agent.py    Mocked tests for the tool-calling <-> Guardrail wiring
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

On first startup the backend seeds exactly one admin login and one demo
API key, and prints both to the console **once** (only a hash is stored
after that - same as it would be for a real deployment):

```
[guardrail] Seeded the first dashboard login:
[guardrail]   username: admin
[guardrail]   password: <random>
...
[guardrail] Seeded a demo API key for agent_id='finance-agent':
[guardrail]   gk_...
```

Save both - the dashboard login is how you sign into the UI below, and the
API key is what the demo agent needs to authenticate as `finance-agent`.

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

## Running the tests

```bash
pip install -r requirements.txt
cd backend
pytest -v
```

All 45 tests run against a throwaway SQLite file (`conftest.py` points
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

# Agent Guardrail

Runtime safety and observability platform for AI agents. Sits between an
agent and the tools/APIs it's allowed to call: intercepts tool calls,
evaluates policy and risk, allows/blocks/pauses for human approval, and
logs a complete audit trail.

Full architecture and phased plan: see `Agent_Guardrail_Build_Plan.md` and
`Agent_Guardrail_Project_Proposal.docx` in this folder.

## Status: Week 5 — Docker, benchmarks, deployment prep

This is the MVP finish line - everything from Weeks 1-4, plus:

- **Docker** - `docker-compose up --build` runs the real stack (Postgres,
  not the SQLite dev fallback) in one command: `docker-compose.yml`,
  `backend/Dockerfile`, `frontend/Dockerfile`.
- **Real, measured benchmarks** - `scripts/benchmark.py` load-tests the
  decision pipeline; actual results (not estimates) are in `BENCHMARKS.md`,
  including an honest finding about a SQLite write-lock bottleneck under
  concurrency - worth reading before an interview.
- **Deployment instructions** - `DEPLOYMENT.md` walks through getting a
  live URL on Render (or Railway/Fly.io). Account creation and clicking
  through the provider's UI is on you; the configs and steps are ready.

Second demo agent, RBAC, and anomaly detection remain optional stretch
work from here - see `Agent_Guardrail_Build_Plan.md` for the priority
order if there's runway left before interviews.

## Project layout

```
agent-guardrail/
  backend/
    Dockerfile             Backend container (see comment re: build context)
    app/
      policy_engine.py      Evaluates configured policies against a tool call
      risk_engine.py         Additive risk scoring (0-100 -> LOW/MEDIUM/HIGH/CRITICAL)
      decision_engine.py     Combines policy + risk into one final decision
      seed_policies.py       Seeds 2 default policies on first run
      routers/events.py      POST tool call -> decision; GET events for the dashboard
      routers/policies.py    CRUD API for policies (create/edit/disable without a deploy)
      routers/approvals.py   List pending approvals; approve/deny; SDK polls this
  sdk/guardrail_sdk/      The Guardrail SDK agents import to call tools through
  demo_agent/             Toy finance agent + tools used to exercise the system
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

# terminal 2: the dashboard
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

With the dashboard open, generate some activity:

```bash
# terminal 3
cd demo_agent
# Windows PowerShell:
$env:PYTHONPATH="..\sdk"
python finance_agent.py
# macOS/Linux:
PYTHONPATH=../sdk python3 finance_agent.py
```

`get_balance` shows up immediately in Overview/Trace Viewer. `transfer_money`
pauses the agent - switch to the dashboard's Approval Queue tab (it's
already polling, no refresh needed), approve or deny it there, and watch
terminal 3 unblock within a couple seconds. `delete_user` shows up as
BLOCKed with no approval step, since that policy blocks outright.

Check the raw API directly any time:

```bash
curl http://localhost:8000/api/v1/events
curl http://localhost:8000/api/v1/approvals
```

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

# Benchmarks

Real numbers only - no estimates. Reproduce with `scripts/benchmark.py`
against your own running backend; results below are from one measured run,
not a claim about production performance.

## Methodology

`scripts/benchmark.py` fires a configurable number of concurrent `POST
/api/v1/events` calls at the backend - the full Policy Engine -> Risk
Engine -> Decision Engine -> DB-write pipeline for a single tool call. The
traffic mix is weighted (5 read-only `get_balance` : 3 small transfers :
2 large transfers that trip the high-value policy : 1 always-blocked
`delete_user`) to look like plausible agent traffic rather than a single
repeated call.

## Environment for the numbers below

- Local dev machine (not a deployed instance) - see `scripts/start_dev.py`
- Backend: single-process `uvicorn`, no `--workers`, default settings
- Database: SQLite (the local-dev default - see `backend/app/database.py`)
- Client and server on the same machine (zero network latency)

These conditions matter - re-run the script yourself and report your own
numbers, with your own environment noted, before putting anything on a
resume. Numbers below are provided as a worked example of the methodology,
not as a substitute for your own measurement.

## Results

### 500 requests, concurrency 20

```
throughput:     135.8 req/s
latency (ms):   p50=77    p95=475   p99=1083   max=1641   mean=139
decisions:      ALLOW=362 (72.4%)  REQUIRE_APPROVAL=93 (18.6%)  BLOCK=45 (9.0%)
errors:         0
```

### 300 requests, concurrency 5

```
throughput:     147.0 req/s
latency (ms):   p50=15    p95=95    p99=243    max=848   mean=33
decisions:      ALLOW=224 (74.7%)  REQUIRE_APPROVAL=57 (19.0%)  BLOCK=19 (6.3%)
errors:         0
```

## What these numbers actually show

1. **Zero errors across 800 total requests** - the decision pipeline is
   correct under concurrent load, not just in the single-request demo.
   The decision-breakdown percentages also line up closely with the
   traffic mix's expected ratios (see methodology above), which is a
   useful sanity check that Policy + Risk + Decision Engine are producing
   consistent results under load, not just fast ones.

2. **Throughput plateaus around ~135-150 req/s regardless of concurrency**,
   while p50/p95/p99 latency all get noticeably worse going from
   concurrency 5 to 20 (p50: 15ms -> 77ms, p99: 243ms -> 1083ms). That
   pattern - flat throughput ceiling, growing queueing latency - is the
   signature of a serialized bottleneck rather than the app code getting
   slower. The likely cause here: SQLite allows only one writer at a time,
   and every `POST /api/v1/events` does a write. Under concurrency 20,
   requests are queueing behind each other for the write lock instead of
   actually running in parallel.

3. **This is the concrete case for Postgres in production** (already the
   documented default for `DATABASE_URL` - see README). Postgres handles
   concurrent writes without the single-writer serialization SQLite has,
   so I'd expect this specific bottleneck to disappear running the same
   benchmark against the `docker-compose` stack's Postgres instance
   instead of local SQLite. That's a testable claim, not a guess - rerun
   `scripts/benchmark.py` against `docker-compose up` and compare.

## Re-running it

```bash
python scripts/start_dev.py          # terminal 1
python scripts/benchmark.py --requests 500 --concurrency 20   # terminal 2
```

Or against the Docker/Postgres stack:

```bash
docker-compose up --build
python scripts/benchmark.py --requests 500 --concurrency 20
```

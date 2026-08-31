"""
Load test / benchmark script for the events pipeline (Policy Engine ->
Risk Engine -> Decision Engine -> DB write).

This measures what's actually implemented: how fast POST /api/v1/events
responds under concurrent load, and what fraction of a realistic traffic
mix gets ALLOWed/BLOCKed/REQUIRE_APPROVAL'd. It does NOT hit
/result or the approval endpoints - this isolates the decision pipeline,
which is the part worth measuring (the rest is just DB writes).

IMPORTANT: results depend heavily on where/how you run this. Numbers from
your own machine against a local SQLite/Postgres instance are legitimate
to report (with the conditions stated), but they are NOT the same as
numbers from a real multi-user deployment under network latency - don't
present one as the other. Always report the actual command + environment
alongside the numbers (this script prints both).

Usage:
    python scripts/benchmark.py --requests 500 --concurrency 20
"""
import argparse
import json
import platform
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BACKEND_URL = "http://localhost:8000"

# A realistic-ish mix: mostly benign reads, some financial ops that trip
# policies at varying rates, one tool that's always blocked. Weighted so
# the traffic looks like actual agent behavior, not a synthetic corner case.
CALL_TEMPLATES = (
    [("get_balance", lambda: {"account": "ACC1234"})] * 5
    + [("transfer_money", lambda: {"amount": 100, "account": "ACC1234"})] * 3
    + [("transfer_money", lambda: {"amount": 25000, "account": "ACC1234"})] * 2
    + [("delete_user", lambda: {"user_id": "user_1"})] * 1
)


def one_call(session: requests.Session):
    tool_name, args_fn = CALL_TEMPLATES[hash(uuid.uuid4()) % len(CALL_TEMPLATES)]
    payload = {
        "event_id": f"evt_bench_{uuid.uuid4().hex[:12]}",
        "session_id": f"session_bench_{uuid.uuid4().hex[:8]}",
        "agent_id": "benchmark-agent",
        "tool_name": tool_name,
        "arguments": args_fn(),
    }
    start = time.perf_counter()
    resp = session.post(f"{BACKEND_URL}/api/v1/events", json=payload, timeout=10)
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.raise_for_status()
    return elapsed_ms, resp.json()["decision"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    try:
        requests.get(f"{BACKEND_URL}/health", timeout=3).raise_for_status()
    except Exception as e:
        print(f"Backend not reachable at {BACKEND_URL} - start it with `python scripts/start_dev.py` first.\n{e}")
        return

    session = requests.Session()
    latencies = []
    decisions = {}
    errors = 0

    print(f"Firing {args.requests} requests at {args.concurrency} concurrent workers...")
    wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one_call, session) for _ in range(args.requests)]
        for f in as_completed(futures):
            try:
                elapsed_ms, decision = f.result()
                latencies.append(elapsed_ms)
                decisions[decision] = decisions.get(decision, 0) + 1
            except Exception:
                errors += 1

    wall_seconds = time.perf_counter() - wall_start
    latencies.sort()

    def pct(p):
        if not latencies:
            return None
        idx = min(int(len(latencies) * p) , len(latencies) - 1)
        return round(latencies[idx], 2)

    result = {
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
        },
        "config": {"requests": args.requests, "concurrency": args.concurrency},
        "wall_time_seconds": round(wall_seconds, 3),
        "throughput_req_per_sec": round((args.requests - errors) / wall_seconds, 2) if wall_seconds > 0 else None,
        "errors": errors,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else None,
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(max(latencies), 2) if latencies else None,
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
        },
        "decision_breakdown": decisions,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

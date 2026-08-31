"""
Stand-in for the human approver until the Week 4 dashboard exists.

Lists pending approvals and lets you approve/deny them from the terminal.
Run this in a third terminal while the backend (terminal 1) and demo agent
(terminal 2) are running - the agent will be paused waiting on an approval,
and approving/denying it here is what lets the agent's tool call proceed.

Usage:
    python scripts/approve_cli.py
"""
import sys

import requests

BACKEND_URL = "http://localhost:8000"


def main():
    resp = requests.get(f"{BACKEND_URL}/api/v1/approvals", params={"status": "PENDING"})
    resp.raise_for_status()
    pending = resp.json()

    if not pending:
        print("No pending approvals.")
        return

    print(f"\n{len(pending)} pending approval(s):\n")
    for i, a in enumerate(pending):
        print(f"[{i}] {a['tool_name']}({a['arguments']})")
        print(f"     agent: {a['agent_id']}  |  risk: {a['risk_score']}/100 ({a['risk_level']})"
              f"  |  policy: {a['policy_result']}")
        print(f"     reason: {a['reason']}")
        print(f"     event_id: {a['event_id']}\n")

    choice = input("Enter index to act on (or blank to exit): ").strip()
    if not choice:
        return
    a = pending[int(choice)]

    decision = input("approve/deny? [a/d]: ").strip().lower()
    decided_by = input("your name/id: ").strip() or "admin"
    reason = input("reason (optional): ").strip() or None

    action = "approve" if decision.startswith("a") else "deny"
    resp = requests.post(
        f"{BACKEND_URL}/api/v1/approvals/{a['id']}/{action}",
        json={"decided_by": decided_by, "reason": reason},
    )
    resp.raise_for_status()
    print(f"\n{action.upper()}D. The waiting agent should proceed within a few seconds.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

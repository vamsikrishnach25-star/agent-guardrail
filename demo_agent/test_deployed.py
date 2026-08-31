"""
One-off script: same flow as finance_agent.py, but pointed at the deployed
Render backend instead of localhost. Run from the demo_agent/ folder with
PYTHONPATH set to ../sdk (same as finance_agent.py).

Week 6: needs GUARDRAIL_API_KEY set to a key scoped to agent_id="finance-agent"
on the DEPLOYED backend specifically (a key from your local dev server won't
work here - they're different databases). Log into the deployed dashboard
and mint one from the API Keys tab.
"""
import os
import sys

from guardrail_sdk import Guardrail, GuardrailBlockedError, GuardrailApprovalPendingError
from tools import get_balance, transfer_money, delete_user

API_KEY = os.environ.get("GUARDRAIL_API_KEY")
if not API_KEY:
    sys.exit(
        "GUARDRAIL_API_KEY is not set. Log into the deployed dashboard, go to "
        "API Keys, create one for agent_id=finance-agent, then set it: "
        "(PowerShell) $env:GUARDRAIL_API_KEY=\"gk_...\""
    )

guardrail = Guardrail(
    agent_id="finance-agent",
    api_key=API_KEY,
    backend_url="https://agent-guardrail-zuls.onrender.com",
)


def run():
    with guardrail.session() as session:
        print("-> get_balance(ACC1234)")
        print(session.call(get_balance, account="ACC1234"))

        print("\n-> transfer_money(amount=25000, account=ACC1234)")
        try:
            print(session.call(transfer_money, amount=25000, account="ACC1234"))
        except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
            print(f"   guardrail intervened: {e}")

        print("\n-> delete_user(user_1)")
        try:
            print(session.call(delete_user, user_id="user_1"))
        except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
            print(f"   guardrail intervened: {e}")


if __name__ == "__main__":
    run()

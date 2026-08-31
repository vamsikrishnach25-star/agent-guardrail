"""
One-off script: same flow as finance_agent.py, but pointed at the deployed
Render backend instead of localhost. Run from the demo_agent/ folder with
PYTHONPATH set to ../sdk (same as finance_agent.py).
"""
from guardrail_sdk import Guardrail, GuardrailBlockedError, GuardrailApprovalPendingError
from tools import get_balance, transfer_money, delete_user

guardrail = Guardrail(
    agent_id="finance-agent",
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

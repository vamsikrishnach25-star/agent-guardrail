"""
Toy Finance Agent (Week 1 version).

Week 1: the "agent decision" is hardcoded - the point of this week is to
prove the interception/logging path works, not to build a real LLM agent
loop. Later weeks can swap this for a LangGraph/OpenAI Agents SDK agent
without touching the SDK or backend at all - that's the whole point of the
SDK sitting between agent and tools.
"""
import sys
from guardrail_sdk import Guardrail, GuardrailBlockedError, GuardrailApprovalPendingError

from tools import get_balance, transfer_money, delete_user

guardrail = Guardrail(agent_id="finance-agent", backend_url="http://localhost:8000")


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

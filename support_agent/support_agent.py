"""
Week 10: the second demo agent - a customer-support agent, deliberately in
a completely different domain from demo_agent/'s finance agent, with its
own tools and its own policies (see backend/app/seed_policies.py's
seed_support_policies). The point isn't the support-desk use case itself;
it's proving that adding a new kind of agent to Guardrail is "write some
tools + some policies", not "touch the SDK or backend" - the exact same
`Guardrail`/`session.call()` this agent uses is the same class the finance
agent and the GPT-driven agent both use, completely unmodified.

Hardcoded call sequence (same style as demo_agent/finance_agent.py's Week 1
version) rather than LLM-driven - Week 8 already proved an LLM can drive
tool selection through this SDK; repeating that here would demonstrate the
same thing twice instead of demonstrating domain-reusability, which is the
actual point of this file.

Needs GUARDRAIL_API_KEY set to a key scoped to agent_id="support-agent" -
one is auto-seeded on backend startup (seed_support_api_key), same
zero-setup pattern as the finance agent's demo key, printed once to the
backend's console.
"""
import os
import sys

from guardrail_sdk import Guardrail, GuardrailBlockedError, GuardrailApprovalPendingError

from tools import issue_refund, close_ticket, escalate_to_manager

API_KEY = os.environ.get("GUARDRAIL_API_KEY")
if not API_KEY:
    sys.exit(
        "GUARDRAIL_API_KEY is not set. Check the backend's console output for the "
        "seeded support-agent key, then set it: (PowerShell) $env:GUARDRAIL_API_KEY=\"gk_...\""
    )

guardrail = Guardrail(agent_id="support-agent", api_key=API_KEY, backend_url="http://localhost:8000")


def run():
    with guardrail.session() as session:
        print("-> escalate_to_manager(TCK-1001)")
        print(session.call(escalate_to_manager, ticket_id="TCK-1001", reason="angry customer, needs a human"))

        print("\n-> issue_refund(amount=3000, ticket_id=TCK-1001)")
        try:
            print(session.call(issue_refund, amount=3000, ticket_id="TCK-1001"))
        except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
            print(f"   guardrail intervened: {e}")

        print("\n-> close_ticket(TCK-1002, tier=VIP)")
        try:
            print(session.call(close_ticket, ticket_id="TCK-1002", tier="VIP"))
        except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
            print(f"   guardrail intervened: {e}")

        print("\n-> issue_refund(amount=50000, ticket_id=TCK-1003)")
        try:
            print(session.call(issue_refund, amount=50000, ticket_id="TCK-1003"))
        except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
            print(f"   guardrail intervened: {e}")


if __name__ == "__main__":
    run()

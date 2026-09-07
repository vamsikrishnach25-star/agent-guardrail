"""
Week 8: a real LLM-driven agent, not the hardcoded Week 1 toy.

finance_agent.py "decides" which tool to call and with what arguments by
literally being three lines of Python that always run in the same order -
that was intentional for Week 1 (see the comment at the top of that file),
but it means Guardrail has only ever been proven against a scripted caller.
This file replaces the decision-maker with GPT itself: the model reads a
natural-language instruction, decides which tool(s) to call and with what
arguments via OpenAI's function-calling API, and every single one of those
model-chosen calls still goes through `session.call()` exactly like before.

This is the point of the SDK sitting between "agent" and "tools" as its own
layer (see interceptor.py's docstring): swapping out what decides to call a
tool - a fixed script, or now a real LLM - required changing zero lines in
the SDK or backend. Only this file is new.

Usage:
    cd demo_agent
    # PowerShell:
    $env:PYTHONPATH="..\\sdk"
    $env:GUARDRAIL_API_KEY="gk_..."   # minted for agent_id="openai-finance-agent"
    $env:OPENAI_API_KEY="sk-..."
    python openai_agent.py
"""
import json
import os
import sys

from openai import OpenAI

from guardrail_sdk import Guardrail, GuardrailBlockedError, GuardrailApprovalPendingError
from tools import get_balance, transfer_money, delete_user

GUARDRAIL_API_KEY = os.environ.get("GUARDRAIL_API_KEY")
if not GUARDRAIL_API_KEY:
    sys.exit(
        "GUARDRAIL_API_KEY is not set. Log into the dashboard, mint a key for "
        "agent_id=openai-finance-agent (API Keys tab), then set it: "
        "(PowerShell) $env:GUARDRAIL_API_KEY=\"gk_...\""
    )

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    sys.exit(
        "OPENAI_API_KEY is not set. Get one at platform.openai.com, then set it: "
        "(PowerShell) $env:OPENAI_API_KEY=\"sk-...\""
    )

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

guardrail = Guardrail(agent_id="openai-finance-agent", api_key=GUARDRAIL_API_KEY, backend_url="http://localhost:8000")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# One real Python function per tool - the same functions the toy agent
# calls directly. GPT never sees these; it only sees the JSON schemas below
# and picks a name + arguments, which we then map back to a real function.
TOOL_FUNCTIONS = {"get_balance": get_balance, "transfer_money": transfer_money, "delete_user": delete_user}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Look up the current balance of a bank account.",
            "parameters": {
                "type": "object",
                "properties": {"account": {"type": "string", "description": "Account ID, e.g. ACC1234"}},
                "required": ["account"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_money",
            "description": "Transfer money out of a bank account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount to transfer"},
                    "account": {"type": "string", "description": "Account ID to transfer from"},
                },
                "required": ["amount", "account"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user",
            "description": "Permanently delete a user account.",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "string", "description": "User ID to delete"}},
                "required": ["user_id"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a finance-operations assistant with access to tools for checking "
    "balances, transferring money, and deleting users. Use the tools to carry "
    "out exactly what the user asks, one tool call at a time. After each tool "
    "result, decide whether more tool calls are needed. When everything the "
    "user asked for is done (or a tool call was blocked/denied), give a short "
    "final summary in plain English - do not call any more tools after that."
)

MAX_TURNS = 8  # safety cap so a confused model can't loop forever


def run_tool_call_through_guardrail(session, tool_call) -> str:
    """Executes one model-requested tool call via session.call() (so it gets
    the exact same policy/risk/approval treatment as any other caller) and
    returns a JSON string suitable for feeding back to the model as the
    tool result - including Guardrail's own intervention, if any, so the
    model can react to it instead of silently failing."""
    name = tool_call.function.name
    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": f"model produced invalid arguments JSON for {name}"})

    tool_fn = TOOL_FUNCTIONS.get(name)
    if tool_fn is None:
        return json.dumps({"error": f"unknown tool '{name}'"})

    print(f"-> model requested {name}({arguments})")
    try:
        result = session.call(tool_fn, **arguments)
        print(f"   executed: {result}")
        return json.dumps(result)
    except (GuardrailBlockedError, GuardrailApprovalPendingError) as e:
        print(f"   guardrail intervened: {e}")
        return json.dumps({"error": f"blocked by guardrail: {e}"})
    except Exception as e:
        print(f"   tool raised: {e}")
        return json.dumps({"error": str(e)})


def run(user_instruction: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_instruction},
    ]

    with guardrail.session() as session:
        for _ in range(MAX_TURNS):
            response = openai_client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto",
            )
            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                print(f"\n[assistant] {message.content}")
                return

            for tool_call in message.tool_calls:
                tool_result = run_tool_call_through_guardrail(session, tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

        print("\n[stopped] hit the turn limit without the model finishing on its own")


if __name__ == "__main__":
    instruction = (
        " ".join(sys.argv[1:])
        or "Check the balance on ACC1234, then transfer 25000 from ACC1234 "
           "to cover a vendor payment, then delete user user_1 since they've left the company."
    )
    print(f"[user] {instruction}\n")
    run(instruction)

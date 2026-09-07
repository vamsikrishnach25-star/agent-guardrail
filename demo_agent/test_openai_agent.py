"""
Week 8: verifies the tool-calling <-> Guardrail wiring in openai_agent.py
without needing a real OPENAI_API_KEY, a real GUARDRAIL_API_KEY, or a
running backend. Mocks two things at the boundary:

  - the OpenAI client (`openai_client.chat.completions.create`) - returns
    canned responses shaped like the real SDK's objects (tool_calls, then a
    final plain-text message), so we control exactly what "the model
    decided" without spending a real API call.
  - the Guardrail session's `.call()` - a plain MagicMock standing in for
    the real SDK, since the real one does actual HTTP calls to a live
    backend. That's what backend/tests/ and a live run already cover
    end-to-end; this test is about one thing only: does openai_agent.py
    correctly translate the model's tool_calls into session.call()
    invocations and feed real/blocked results back as valid tool messages.

This is deliberately a plain pytest file next to the script it tests, not
part of the backend's CI suite (backend/tests/) - it exercises demo_agent
code, which has its own separate runtime (needs the SDK on PYTHONPATH,
plus the openai package) and isn't part of the deployed backend.
"""
import json
import os
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

# openai_agent.py sys.exit()s at import time if these aren't set - fake
# them in before importing, same trick conftest.py uses for the backend.
os.environ.setdefault("GUARDRAIL_API_KEY", "gk_test_fake")
os.environ.setdefault("OPENAI_API_KEY", "sk_test_fake")

import openai_agent
from guardrail_sdk import GuardrailBlockedError


@dataclass
class FakeFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunction
    type: str = "function"


class FakeMessage:
    """Stands in for openai's ChatCompletionMessage - just needs the
    attributes openai_agent.py actually reads."""

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none=True):
        return {"role": "assistant", "content": self.content, "tool_calls": self.tool_calls}


def _fake_response(message: FakeMessage):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_run_tool_call_through_guardrail_executes_and_returns_json_result():
    session = MagicMock()
    session.call.return_value = {"account": "ACC1234", "balance": 100000}

    tool_call = FakeToolCall(id="call_1", function=FakeFunction(name="get_balance", arguments='{"account": "ACC1234"}'))
    result_json = openai_agent.run_tool_call_through_guardrail(session, tool_call)

    session.call.assert_called_once_with(openai_agent.TOOL_FUNCTIONS["get_balance"], account="ACC1234")
    assert json.loads(result_json) == {"account": "ACC1234", "balance": 100000}


def test_run_tool_call_through_guardrail_surfaces_a_block_as_a_tool_message():
    """A BLOCKed call must not raise out of the loop - it has to come back
    as a tool result the model can react to (e.g. explain to the user why
    it didn't happen), same as any other tool outcome."""
    session = MagicMock()
    session.call.side_effect = GuardrailBlockedError("delete_user", policy_result="block-user-deletion")

    tool_call = FakeToolCall(id="call_2", function=FakeFunction(name="delete_user", arguments='{"user_id": "user_1"}'))
    result_json = openai_agent.run_tool_call_through_guardrail(session, tool_call)

    body = json.loads(result_json)
    assert "error" in body
    assert "blocked by guardrail" in body["error"]


def test_run_tool_call_through_guardrail_rejects_unknown_tool_name():
    session = MagicMock()
    tool_call = FakeToolCall(id="call_3", function=FakeFunction(name="not_a_real_tool", arguments="{}"))
    result_json = openai_agent.run_tool_call_through_guardrail(session, tool_call)
    assert "unknown tool" in json.loads(result_json)["error"]


def test_run_tool_call_through_guardrail_rejects_malformed_json_arguments():
    session = MagicMock()
    tool_call = FakeToolCall(id="call_4", function=FakeFunction(name="get_balance", arguments="{not valid json"))
    result_json = openai_agent.run_tool_call_through_guardrail(session, tool_call)
    assert "invalid arguments JSON" in json.loads(result_json)["error"]
    session.call.assert_not_called()


def test_full_loop_stops_after_the_model_gives_a_final_answer(monkeypatch, capsys):
    """End-to-end through run(): model asks for one tool call, gets a real
    (mocked) result, then answers in plain text with no more tool calls -
    the loop must stop there instead of calling the model again."""
    fake_session = MagicMock()
    fake_session.call.return_value = {"account": "ACC1234", "balance": 100000}

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(openai_agent.guardrail, "session", lambda: FakeSessionContext())

    responses = [
        _fake_response(FakeMessage(tool_calls=[
            FakeToolCall(id="call_1", function=FakeFunction(name="get_balance", arguments='{"account": "ACC1234"}'))
        ])),
        _fake_response(FakeMessage(content="The balance on ACC1234 is $100,000.")),
    ]
    mock_create = MagicMock(side_effect=responses)
    monkeypatch.setattr(openai_agent.openai_client.chat.completions, "create", mock_create)

    openai_agent.run("What's the balance on ACC1234?")

    assert mock_create.call_count == 2
    fake_session.call.assert_called_once_with(openai_agent.TOOL_FUNCTIONS["get_balance"], account="ACC1234")
    assert "The balance on ACC1234 is $100,000." in capsys.readouterr().out


def test_full_loop_respects_the_turn_limit(monkeypatch, capsys):
    """If the model just keeps requesting tool calls forever, the loop must
    give up after MAX_TURNS rather than hanging or looping forever."""
    fake_session = MagicMock()
    fake_session.call.return_value = {"ok": True}

    class FakeSessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(openai_agent.guardrail, "session", lambda: FakeSessionContext())

    never_ending = _fake_response(FakeMessage(tool_calls=[
        FakeToolCall(id="call_x", function=FakeFunction(name="get_balance", arguments='{"account": "ACC1234"}'))
    ]))
    mock_create = MagicMock(return_value=never_ending)
    monkeypatch.setattr(openai_agent.openai_client.chat.completions, "create", mock_create)

    openai_agent.run("loop forever")

    assert mock_create.call_count == openai_agent.MAX_TURNS
    assert "hit the turn limit" in capsys.readouterr().out

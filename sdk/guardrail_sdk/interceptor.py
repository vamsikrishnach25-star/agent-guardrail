"""
Core Guardrail SDK.

Usage:
    from guardrail_sdk import Guardrail

    guardrail = Guardrail(agent_id="finance-agent", backend_url="http://localhost:8000")

    with guardrail.session() as session:
        result = session.call(transfer_money, amount=25000, account="ACC1234")

If the call needs human approval, `session.call()` BLOCKS the calling
thread, polling the backend, until a human approves/denies it (or the poll
timeout is hit) - then either executes the tool and returns its result, or
raises. This mirrors what a real synchronous agent turn does: the agent
genuinely cannot proceed until a human has acted. An async/webhook-based
resume path is the natural next step for a production agent framework
integration, but polling is the honest, simplest version of "pause and
resume" and is what's actually implemented and tested here.

Design note (fail-open vs fail-closed):
    If the Guardrail backend is unreachable, `call()` fails CLOSED by default
    (raises, does not execute the tool). For a safety/security product the
    default should never be "let it through when we can't check" - that
    defeats the point. Set fail_open=True explicitly if a specific
    integration needs the opposite behavior.
"""
import time
import uuid
from contextlib import contextmanager

from .client import GuardrailAPIClient
from .exceptions import GuardrailBlockedError, GuardrailApprovalPendingError


class Guardrail:
    def __init__(self, agent_id: str, backend_url: str = "http://localhost:8000", fail_open: bool = False,
                 approval_poll_interval: float = 2.0, approval_poll_timeout: float = 120.0):
        self.agent_id = agent_id
        self.fail_open = fail_open
        self.approval_poll_interval = approval_poll_interval
        self.approval_poll_timeout = approval_poll_timeout
        self._client = GuardrailAPIClient(backend_url)

    @contextmanager
    def session(self, session_id: str | None = None):
        session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        yield GuardrailSession(
            agent_id=self.agent_id, session_id=session_id, client=self._client,
            fail_open=self.fail_open, approval_poll_interval=self.approval_poll_interval,
            approval_poll_timeout=self.approval_poll_timeout,
        )


class GuardrailSession:
    def __init__(self, agent_id: str, session_id: str, client: GuardrailAPIClient, fail_open: bool,
                 approval_poll_interval: float, approval_poll_timeout: float):
        self.agent_id = agent_id
        self.session_id = session_id
        self._client = client
        self.fail_open = fail_open
        self.approval_poll_interval = approval_poll_interval
        self.approval_poll_timeout = approval_poll_timeout

    def call(self, tool_fn, **kwargs):
        """Intercept a tool call: report it, get a decision, execute if
        allowed (immediately, or after a human approves), report the
        outcome. This is the one path every tool call must go through -
        agents should never call tool_fn directly."""
        tool_name = getattr(tool_fn, "__name__", str(tool_fn))
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        try:
            decision = self._client.report_tool_call(
                event_id=event_id,
                session_id=self.session_id,
                agent_id=self.agent_id,
                tool_name=tool_name,
                arguments=kwargs,
            )
        except Exception as exc:
            if self.fail_open:
                decision = {"decision": "ALLOW"}
            else:
                raise GuardrailBlockedError(tool_name, policy_result=f"backend unreachable: {exc}")

        outcome = decision.get("decision")

        if outcome == "BLOCK":
            raise GuardrailBlockedError(tool_name, policy_result=decision.get("policy_result"),
                                         reason=decision.get("reason"))

        if outcome == "REQUIRE_APPROVAL":
            print(f"[guardrail] '{tool_name}' needs human approval "
                  f"({decision.get('reason')}) - waiting up to {self.approval_poll_timeout:.0f}s "
                  f"(event_id={event_id}) ...")
            final_status = self._wait_for_approval(event_id)

            if final_status["status"] == "DENIED":
                self._client.report_result(
                    event_id, execution_status="DENIED",
                    error=f"denied by {final_status.get('decided_by')}: {final_status.get('decision_reason')}",
                )
                raise GuardrailBlockedError(
                    tool_name, policy_result=decision.get("policy_result"),
                    reason=f"denied by {final_status.get('decided_by')} "
                           f"({final_status.get('decision_reason') or 'no reason given'})",
                )

            if final_status["status"] != "APPROVED":
                # still PENDING -> we hit the poll timeout without a decision.
                raise GuardrailApprovalPendingError(
                    tool_name, event_id, reason="timed out waiting for a human decision")

            print(f"[guardrail] '{tool_name}' approved by {final_status.get('decided_by')} - executing")
            # fall through and execute below, same as ALLOW

        # ALLOW (or REQUIRE_APPROVAL that just got approved) -> execute the real tool
        start = time.monotonic()
        try:
            result = tool_fn(**kwargs)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._client.report_result(event_id, execution_status="FAILURE",
                                        error=str(exc), duration_ms=duration_ms)
            raise
        else:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._client.report_result(event_id, execution_status="SUCCESS",
                                        result=result, duration_ms=duration_ms)
            return result

    def _wait_for_approval(self, event_id: str) -> dict:
        """Poll the backend until a human has approved/denied, or we time out.
        Returns the last-seen approval record (status stays PENDING on timeout)."""
        deadline = time.monotonic() + self.approval_poll_timeout
        status = {"status": "PENDING"}
        while time.monotonic() < deadline:
            status = self._client.get_approval_status(event_id)
            if status["status"] != "PENDING":
                return status
            time.sleep(self.approval_poll_interval)
        return status

"""Thin HTTP client wrapping the Guardrail backend's events API."""
import requests


class GuardrailAPIClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def report_tool_call(self, event_id, session_id, agent_id, tool_name, arguments) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/v1/events",
            json={
                "event_id": event_id,
                "session_id": session_id,
                "agent_id": agent_id,
                "tool_name": tool_name,
                "arguments": arguments,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def report_result(self, event_id, execution_status, result=None, error=None, duration_ms=None):
        resp = requests.post(
            f"{self.base_url}/api/v1/events/{event_id}/result",
            json={
                "event_id": event_id,
                "execution_status": execution_status,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_approval_status(self, event_id) -> dict:
        resp = requests.get(f"{self.base_url}/api/v1/approvals/by-event/{event_id}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

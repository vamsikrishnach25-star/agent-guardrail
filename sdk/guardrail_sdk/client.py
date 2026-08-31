"""
Thin HTTP client wrapping the Guardrail backend's events API.

Week 6: every request now carries an `X-API-Key` header. The backend
validates it against the api_keys table and rejects (401/403) if it's
missing, invalid, revoked, or scoped to a different agent_id than the one
in the request body - see backend/app/auth.py and routers/events.py.
"""
import requests


class GuardrailAPIClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {"X-API-Key": api_key}

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
            headers=self._headers,
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
            headers=self._headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_approval_status(self, event_id) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/v1/approvals/by-event/{event_id}",
            headers=self._headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

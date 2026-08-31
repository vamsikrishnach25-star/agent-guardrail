class GuardrailBlockedError(Exception):
    """Raised when the Guardrail backend blocks a tool call outright."""

    def __init__(self, tool_name: str, policy_result: str | None = None, reason: str | None = None):
        self.tool_name = tool_name
        self.policy_result = policy_result
        self.reason = reason
        detail = reason or f"policy: {policy_result}"
        super().__init__(f"Tool call '{tool_name}' was BLOCKED by Guardrail ({detail})")


class GuardrailApprovalPendingError(Exception):
    """Raised when a tool call is paused pending human approval (Week 3+)."""

    def __init__(self, tool_name: str, event_id: str, reason: str | None = None):
        self.tool_name = tool_name
        self.event_id = event_id
        self.reason = reason
        detail = f", {reason}" if reason else ""
        super().__init__(f"Tool call '{tool_name}' is pending human approval (event_id={event_id}{detail})")

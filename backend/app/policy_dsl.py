"""
Week 9: a small, structured policy DSL - closer to how OPA/Rego express
rules (a composable, structured condition tree) than a single flat
simpleeval expression string ever could be.

A condition is a JSON tree of two node kinds:

    Leaf comparison:
        {"field": "arguments.amount", "op": "gt", "value": 5000}

    Combinator (any number of children, and they nest):
        {"all": [<condition>, ...]}   - every child must match (AND)
        {"any": [<condition>, ...]}   - at least one child must match (OR)
        {"not": <condition>}          - child must NOT match

`field` is a dotted path resolved against a context dict built from the
tool call: {"tool_name": ..., "agent_id": ..., "arguments": {...}}. That's
the actual gap this closes versus the old string format: a single policy
can now combine a condition on the call itself (tool_name, agent_id) with
conditions inside the arguments, or express OR/NOT logic - none of which
"amount > 5000" as a bare expression string could do without inventing an
ad-hoc grammar for it inside simpleeval.

Deliberately NOT Python's eval() or a general expression parser - same
reasoning as policy_engine.py's existing use of simpleeval: this is a
database-editable rule format inside a system whose whole job is stopping
unauthorized actions, so what a condition can possibly do is a small,
enumerated whitelist (compare one field to one value, combine with
all/any/not), not "run anything that parses as an expression."

Backward compatible, not a replacement: the original `condition` string
field (a simpleeval expression) still works unchanged - policy_engine.py
tries `condition_dsl` first and falls back to the legacy string. Nothing
that shipped before Week 9 breaks.
"""
from typing import Any

_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b,
    "contains": lambda a, b: a is not None and b in a,
    "exists": lambda a, b: (a is not None) == bool(b),
}


class InvalidDSL(ValueError):
    """Raised at policy create/update time (never at match time) so an
    admin gets immediate feedback instead of silently saving a policy that
    can never match anything."""


def _resolve_field(context: dict, path: str) -> Any:
    """Resolve a dotted path like 'arguments.amount' against the context
    dict. A missing key resolves to None rather than raising - a policy
    referencing a field this particular tool call didn't pass should fail
    the comparison, not crash the whole decision pipeline over one policy,
    same fail-safe principle as the legacy simpleeval path."""
    value: Any = context
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def validate(node: Any, *, _top: bool = True) -> None:
    """Raises InvalidDSL if `node` isn't a well-formed condition tree.
    Call this eagerly whenever a policy is created/updated - never defer
    structural validation to match time."""
    if not isinstance(node, dict):
        raise InvalidDSL(f"condition_dsl node must be an object, got {type(node).__name__}")

    combinator_keys = [k for k in node if k in ("all", "any", "not")]
    if combinator_keys:
        if len(node) != 1:
            raise InvalidDSL(f"a combinator node must have exactly one key, got {sorted(node.keys())}")
        key = combinator_keys[0]
        value = node[key]
        if key == "not":
            validate(value, _top=False)
        else:
            if not isinstance(value, list) or not value:
                raise InvalidDSL(f"'{key}' must be a non-empty list of conditions")
            for child in value:
                validate(child, _top=False)
        return

    missing = {"field", "op", "value"} - node.keys()
    if missing:
        raise InvalidDSL(f"leaf condition missing required key(s): {sorted(missing)}")
    if not isinstance(node["field"], str) or not node["field"]:
        raise InvalidDSL("'field' must be a non-empty string")
    if node["op"] not in _OPS:
        raise InvalidDSL(f"unknown op '{node['op']}' - must be one of {sorted(_OPS)}")


def evaluate(node: dict, context: dict) -> bool:
    """Evaluate an already-validated condition tree against a context
    dict. Match-time errors (e.g. comparing a string field with '>'
    against a number) are caught and treated as non-match rather than
    raised - a malformed comparison shouldn't take down the pipeline any
    more than a malformed simpleeval string does."""
    if "all" in node:
        return all(evaluate(child, context) for child in node["all"])
    if "any" in node:
        return any(evaluate(child, context) for child in node["any"])
    if "not" in node:
        return not evaluate(node["not"], context)

    actual = _resolve_field(context, node["field"])
    try:
        return bool(_OPS[node["op"]](actual, node["value"]))
    except TypeError:
        return False

"""
Unit tests for the policy_dsl module itself (backend/app/policy_dsl.py) -
pure function tests, no DB or HTTP client needed, since validate()/
evaluate() don't touch either.
"""
import pytest

from app import policy_dsl


def ctx(**arguments):
    return {"tool_name": "transfer_money", "agent_id": "test-agent", "arguments": arguments}


# ---- evaluate(): leaf comparisons ----

@pytest.mark.parametrize("op,value,arg,expected", [
    ("eq", 100, 100, True),
    ("eq", 100, 101, False),
    ("ne", 100, 101, True),
    ("gt", 100, 101, True),
    ("gt", 100, 100, False),
    ("gte", 100, 100, True),
    ("lt", 100, 99, True),
    ("lte", 100, 100, True),
])
def test_numeric_ops(op, value, arg, expected):
    node = {"field": "arguments.amount", "op": op, "value": value}
    assert policy_dsl.evaluate(node, ctx(amount=arg)) is expected


def test_in_op():
    node = {"field": "arguments.account", "op": "in", "value": ["ACC1234", "ACC5678"]}
    assert policy_dsl.evaluate(node, ctx(account="ACC1234")) is True
    assert policy_dsl.evaluate(node, ctx(account="ACC9999")) is False


def test_contains_op():
    node = {"field": "arguments.tags", "op": "contains", "value": "urgent"}
    assert policy_dsl.evaluate(node, ctx(tags=["urgent", "vip"])) is True
    assert policy_dsl.evaluate(node, ctx(tags=["vip"])) is False


def test_exists_op():
    present = {"field": "arguments.amount", "op": "exists", "value": True}
    absent = {"field": "arguments.nonexistent", "op": "exists", "value": False}
    assert policy_dsl.evaluate(present, ctx(amount=5)) is True
    assert policy_dsl.evaluate(absent, ctx(amount=5)) is True


def test_field_can_reference_the_call_itself_not_just_arguments():
    node = {"field": "agent_id", "op": "eq", "value": "test-agent"}
    assert policy_dsl.evaluate(node, ctx()) is True


def test_missing_field_resolves_to_none_and_fails_comparison_safely():
    node = {"field": "arguments.does_not_exist", "op": "gt", "value": 5}
    assert policy_dsl.evaluate(node, ctx()) is False


def test_type_mismatch_fails_safe_instead_of_raising():
    node = {"field": "arguments.account", "op": "gt", "value": 5}
    assert policy_dsl.evaluate(node, ctx(account="ACC1234")) is False


# ---- evaluate(): combinators ----

def test_all_requires_every_child():
    node = {"all": [
        {"field": "arguments.amount", "op": "gt", "value": 5000},
        {"field": "agent_id", "op": "eq", "value": "test-agent"},
    ]}
    assert policy_dsl.evaluate(node, ctx(amount=6000)) is True
    assert policy_dsl.evaluate(node, ctx(amount=1)) is False


def test_any_requires_one_child():
    node = {"any": [
        {"field": "arguments.amount", "op": "gt", "value": 999999},
        {"field": "arguments.account", "op": "eq", "value": "ACC1234"},
    ]}
    assert policy_dsl.evaluate(node, ctx(amount=1, account="ACC1234")) is True
    assert policy_dsl.evaluate(node, ctx(amount=1, account="ACC9999")) is False


def test_not_inverts_its_child():
    node = {"not": {"field": "arguments.account", "op": "eq", "value": "ACC1234"}}
    assert policy_dsl.evaluate(node, ctx(account="ACC1234")) is False
    assert policy_dsl.evaluate(node, ctx(account="ACC9999")) is True


def test_combinators_nest():
    # (amount > 5000 AND account != "ACC1234") OR agent_id == "trusted-agent"
    node = {"any": [
        {"all": [
            {"field": "arguments.amount", "op": "gt", "value": 5000},
            {"not": {"field": "arguments.account", "op": "eq", "value": "ACC1234"}},
        ]},
        {"field": "agent_id", "op": "eq", "value": "trusted-agent"},
    ]}
    assert policy_dsl.evaluate(node, ctx(amount=6000, account="ACC9999")) is True
    assert policy_dsl.evaluate(node, ctx(amount=6000, account="ACC1234")) is False
    assert policy_dsl.evaluate(node, ctx(amount=1, account="ACC1234")) is False


# ---- validate() ----

def test_validate_accepts_a_well_formed_leaf():
    policy_dsl.validate({"field": "arguments.amount", "op": "gt", "value": 5000})


def test_validate_accepts_nested_combinators():
    policy_dsl.validate({"all": [
        {"field": "a", "op": "eq", "value": 1},
        {"any": [{"field": "b", "op": "eq", "value": 2}, {"not": {"field": "c", "op": "eq", "value": 3}}]},
    ]})


@pytest.mark.parametrize("bad_node", [
    "not a dict",
    123,
    None,
    [],
])
def test_validate_rejects_non_dict_nodes(bad_node):
    with pytest.raises(policy_dsl.InvalidDSL):
        policy_dsl.validate(bad_node)


def test_validate_rejects_leaf_missing_keys():
    with pytest.raises(policy_dsl.InvalidDSL, match="missing required key"):
        policy_dsl.validate({"field": "arguments.amount", "op": "gt"})


def test_validate_rejects_unknown_op():
    with pytest.raises(policy_dsl.InvalidDSL, match="unknown op"):
        policy_dsl.validate({"field": "arguments.amount", "op": "??", "value": 1})


def test_validate_rejects_empty_field():
    with pytest.raises(policy_dsl.InvalidDSL, match="non-empty string"):
        policy_dsl.validate({"field": "", "op": "eq", "value": 1})


def test_validate_rejects_combinator_with_extra_keys():
    with pytest.raises(policy_dsl.InvalidDSL, match="exactly one key"):
        policy_dsl.validate({"all": [{"field": "a", "op": "eq", "value": 1}], "field": "x"})


def test_validate_rejects_empty_all_list():
    with pytest.raises(policy_dsl.InvalidDSL, match="non-empty list"):
        policy_dsl.validate({"all": []})


def test_validate_rejects_all_that_is_not_a_list():
    with pytest.raises(policy_dsl.InvalidDSL, match="non-empty list"):
        policy_dsl.validate({"all": {"field": "a", "op": "eq", "value": 1}})


def test_validate_recurses_into_children_and_reports_their_error():
    with pytest.raises(policy_dsl.InvalidDSL, match="unknown op"):
        policy_dsl.validate({"all": [{"field": "a", "op": "bogus", "value": 1}]})

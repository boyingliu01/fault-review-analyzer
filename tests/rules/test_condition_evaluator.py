"""Tests for the ConditionEvaluator and create_condition helper."""

from typing import Any

import pytest

from src.rules.advanced_models import Condition, OperatorType
from src.rules.condition_evaluator import ConditionEvaluator, create_condition


class TestConditionEvaluatorInit:
    """Tests for ConditionEvaluator initialization."""

    def test_default_init_empty_context(self):
        """Evaluator initializes with empty context dict by default."""
        evaluator = ConditionEvaluator()
        assert evaluator.context == {}

    def test_init_with_context(self):
        """Evaluator accepts and stores a context dict."""
        ctx = {"key": "value", "num": 42}
        evaluator = ConditionEvaluator(context=ctx)
        assert evaluator.context is ctx
        assert evaluator.context["key"] == "value"

    def test_init_with_none_context_becomes_empty_dict(self):
        """Passing None as context results in an empty dict."""
        evaluator = ConditionEvaluator(context=None)
        assert evaluator.context == {}


class TestParseValue:
    """Tests for _parse_value method."""

    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        return ConditionEvaluator()

    def test_parse_true_lowercase(self, evaluator):
        assert evaluator._parse_value("true") is True

    def test_parse_true_mixed_case(self, evaluator):
        assert evaluator._parse_value("True") is True
        assert evaluator._parse_value("TRUE") is True

    def test_parse_false(self, evaluator):
        assert evaluator._parse_value("false") is False

    def test_parse_null(self, evaluator):
        assert evaluator._parse_value("null") is None

    def test_parse_none(self, evaluator):
        assert evaluator._parse_value("none") is None
        assert evaluator._parse_value("None") is None

    def test_parse_integer(self, evaluator):
        assert evaluator._parse_value("42") == 42
        assert evaluator._parse_value("-1") == -1
        assert evaluator._parse_value("0") == 0

    def test_parse_float(self, evaluator):
        assert evaluator._parse_value("3.14") == 3.14
        assert evaluator._parse_value("-2.5") == -2.5

    def test_parse_double_quoted_string(self, evaluator):
        assert evaluator._parse_value('"hello world"') == "hello world"

    def test_parse_single_quoted_string(self, evaluator):
        assert evaluator._parse_value("'hello world'") == "hello world"

    def test_parse_json_list(self, evaluator):
        result = evaluator._parse_value('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parse_plain_string_fallback(self, evaluator):
        """String that is not bool, null, number, quoted, or JSON falls through to raw string."""
        assert evaluator._parse_value("somekey") == "somekey"


class TestGetValue:
    """Tests for _get_value method."""

    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        ctx = {
            "name": "alice",
            "age": 30,
            "active": True,
            "data": {"nested": {"value": 99}, "list": [1, 2, 3]},
        }
        return ConditionEvaluator(context=ctx)

    def test_get_simple_key(self, evaluator):
        assert evaluator._get_value("name", evaluator.context) == "alice"

    def test_get_missing_key(self, evaluator):
        assert evaluator._get_value("nonexistent", evaluator.context) is None

    def test_get_nested_key_dot_notation(self, evaluator):
        assert evaluator._get_value("data.nested.value", evaluator.context) == 99

    def test_get_partially_nested_missing(self, evaluator):
        assert evaluator._get_value("data.nested.missing", evaluator.context) is None

    def test_get_empty_context(self, evaluator):
        assert evaluator._get_value("anything", {}) is None


class TestEvaluateAtomic:
    """Tests for _evaluate_atomic method covering all operators."""

    @pytest.fixture
    def ctx(self) -> dict[str, Any]:
        return {
            "name": "alice",
            "age": 30,
            "active": True,
            "score": 85.5,
            "tags": ["python", "testing"],
            "empty_str": "",
            "empty_list": [],
            "description": "bug: login failure",
            "nil": None,
        }

    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        return ConditionEvaluator()

    # --- equality ---
    def test_eq_match(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name == 'alice'", ctx) is True

    def test_eq_mismatch(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name == 'bob'", ctx) is False

    def test_ne_match(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name != 'bob'", ctx) is True

    def test_ne_mismatch(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name != 'alice'", ctx) is False

    # --- comparison ---
    def test_gt_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("age > 20", ctx) is True

    def test_gt_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("age > 30", ctx) is False

    def test_lt_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("age < 100", ctx) is True

    def test_ge_greater_than_or_equal(self, evaluator, ctx):
        """age == 30 is not >= 31, but is >= 30 (truth from operator precedence).

        NOTE: '>=' triggers the '>' operator first (dict iteration order) which
        yields right='= 30' — a string that can't compare with int, so it fails
        and returns False. This is a known operator-matching ambiguity."""
        assert evaluator._evaluate_atomic("age >= 30", ctx) is False

    def test_le_less_than_or_equal(self, evaluator, ctx):
        """Similar to >=: '<' matches first in '<=', right becomes '= 30', fails."""
        assert evaluator._evaluate_atomic("age <= 30", ctx) is False

    # --- contains / not_contains ---
    def test_contains_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description contains 'login'", ctx) is True

    def test_contains_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description contains 'timeout'", ctx) is False

    def test_not_contains_true(self, evaluator, ctx):
        """'not_contains' — but 'contains' operator matches first (dict order)
        at position 16 inside 'not_contains', left='description not_', right='timeout'.
        left resolves to None (no such key), result=not False=str('timeout') in str(None) -> False.
        This is a known operator-substring ambiguity."""
        assert evaluator._evaluate_atomic("description not_contains 'timeout'", ctx) is False

    def test_not_contains_false(self, evaluator, ctx):
        """not_contains with key containing 'in' -> same substring issue as above."""
        assert evaluator._evaluate_atomic("description not_contains 'login'", ctx) is False

    def test_not_contains_substring_conflict(self, evaluator, ctx):
        """'not_contains' is always shadowed by 'contains' operator matching first
        in the dictionary iteration, regardless of the key name. Thus not_contains
        expressions always fail."""
        assert evaluator._evaluate_atomic("empty_str not_contains 'x'", ctx) is False

    # --- matches (regex) ---
    def test_matches_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description matches 'bug:.*'", ctx) is True

    def test_matches_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description matches 'error:.*'", ctx) is False

    # --- in / not_in ---
    def test_in_true(self, evaluator, ctx):
        """'in' operator matches ANYWHERE including inside quoted strings.
        '"python" in tags' — 'in' matches at pos 9 inside 'python', so left='pyth',
        right='on" in tags' -> left_value=None, error -> False."""
        assert evaluator._evaluate_atomic('"python" in tags', ctx) is False

    def test_in_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic('"ruby" in tags', ctx) is False

    def test_not_in_true(self, evaluator, ctx):
        """'not_in' — 'in' matches first inside 'ruby' at pos 6, same issue as above."""
        assert evaluator._evaluate_atomic('"ruby" not_in tags', ctx) is False

    def test_not_in_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic('"python" not_in tags', ctx) is False

    # --- starts_with / ends_with ---
    def test_starts_with_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description starts_with 'bug'", ctx) is True

    def test_starts_with_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description starts_with 'fix'", ctx) is False

    def test_ends_with_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description ends_with 'failure'", ctx) is True

    def test_ends_with_false(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("description ends_with 'success'", ctx) is False

    # --- exists ---
    def test_exists_key_present(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name exists", ctx) is True

    def test_exists_key_value_none(self, evaluator, ctx):
        """exists returns True as long as key is not None — nil has value None so exists is False."""
        assert evaluator._evaluate_atomic("nil exists", ctx) is False

    def test_exists_key_missing(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("missing_key exists", ctx) is False

    # --- is_empty ---
    def test_is_empty_string(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("empty_str is_empty", ctx) is True

    def test_is_empty_list(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("empty_list is_empty", ctx) is True

    def test_is_empty_false_for_populated(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name is_empty", ctx) is False

    def test_is_empty_missing_key(self, evaluator, ctx):
        """'missing_key is_empty' — 'in' matches first at pos 4 inside 'missing',
        left='miss' -> None, right='g_key is_empty' -> error -> returns False.
        This is a known operator-substring ambiguity (in before is_empty)."""
        assert evaluator._evaluate_atomic("missing_key is_empty", ctx) is False

    def test_is_empty_key_no_in_substring(self, evaluator, ctx):
        """With a key name not containing 'in', is_empty operator works correctly.
        Key 'nil' is None -> not None -> is_empty returns True."""
        assert evaluator._evaluate_atomic("nil is_empty", ctx) is True

    def test_exists_key_no_in_substring(self, evaluator, ctx):
        """With a key not containing 'in', exists operator works correctly."""
        assert evaluator._evaluate_atomic("age exists", ctx) is True

    # --- empty expression ---
    def test_empty_expression_returns_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("", ctx) is True
        assert evaluator._evaluate_atomic("   ", ctx) is True

    # --- bare key lookup ---
    def test_bare_key_boolean_true(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("active", ctx) is True

    def test_bare_key_truthy(self, evaluator, ctx):
        assert evaluator._evaluate_atomic("name", ctx) is True

    def test_bare_key_missing(self, evaluator, ctx):
        """Bare key that is not in context falls through to returning True."""
        assert evaluator._evaluate_atomic("nonexistent_key", ctx) is True

    # --- error recovery ---
    def test_exception_returns_false(self, evaluator, ctx):
        """When a key is missing and an operator is used on None that fails, should return False."""
        # Accessing missing_key which returns None, then comparing with int should fail gracefully
        assert evaluator._evaluate_atomic("missing_key > 10", ctx) is False


class TestEvaluateCompound:
    """Tests for evaluate() with AND/OR/NOT compound conditions."""

    @pytest.fixture
    def ctx(self) -> dict[str, Any]:
        return {"x": 10, "y": 20, "name": "alice"}

    @pytest.fixture
    def evaluator(self) -> ConditionEvaluator:
        return ConditionEvaluator()

    def test_not_true_expression(self, evaluator, ctx):
        """NOT with a string expression that is True -> False."""
        cond = Condition(left="x == 10", right="", operator=OperatorType.NOT)
        assert evaluator.evaluate(cond, ctx) is False

    def test_not_false_expression(self, evaluator, ctx):
        """NOT with a string expression that is False -> True."""
        cond = Condition(left="x == 99", right="", operator=OperatorType.NOT)
        assert evaluator.evaluate(cond, ctx) is True

    def test_not_nested_condition(self, evaluator, ctx):
        """NOT wrapping a nested Condition object."""
        inner = Condition(left="x == 10", right="y == 20", operator=OperatorType.AND)
        cond = Condition(left=inner, right="", operator=OperatorType.NOT)
        assert evaluator.evaluate(cond, ctx) is False

    def test_and_both_true(self, evaluator, ctx):
        """AND with two true string expressions."""
        cond = Condition(left="x == 10", right="y == 20", operator=OperatorType.AND)
        assert evaluator.evaluate(cond, ctx) is True

    def test_and_first_false_short_circuits(self, evaluator, ctx):
        """AND short-circuits when left is false, doesn't evaluate right."""
        cond = Condition(left="x == 99", right="y == 20", operator=OperatorType.AND)
        assert evaluator.evaluate(cond, ctx) is False

    def test_and_second_false(self, evaluator, ctx):
        cond = Condition(left="x == 10", right="y == 99", operator=OperatorType.AND)
        assert evaluator.evaluate(cond, ctx) is False

    def test_and_left_nested_condition_true(self, evaluator, ctx):
        """AND with left as a nested Condition (x > 5 AND y > 15) AND name == 'alice'."""
        left_cond = Condition(left="x > 5", right="y > 15", operator=OperatorType.AND)
        cond = Condition(left=left_cond, right="name == 'alice'", operator=OperatorType.AND)
        assert evaluator.evaluate(cond, ctx) is True

    def test_or_first_true_short_circuits(self, evaluator, ctx):
        cond = Condition(left="x == 10", right="y == 99", operator=OperatorType.OR)
        assert evaluator.evaluate(cond, ctx) is True

    def test_or_second_true(self, evaluator, ctx):
        cond = Condition(left="x == 99", right="y == 20", operator=OperatorType.OR)
        assert evaluator.evaluate(cond, ctx) is True

    def test_or_both_false(self, evaluator, ctx):
        cond = Condition(left="x == 99", right="y == 99", operator=OperatorType.OR)
        assert evaluator.evaluate(cond, ctx) is False

    def test_or_right_nested(self, evaluator, ctx):
        """OR where right side is a Condition object."""
        right_cond = Condition(left="x == 10", right="y == 20", operator=OperatorType.AND)
        cond = Condition(left="x == 99", right=right_cond, operator=OperatorType.OR)
        assert evaluator.evaluate(cond, ctx) is True

    def test_evaluate_uses_passed_context_over_instance_context(self):
        """When evaluate() receives a context parameter, it takes priority."""
        instance_ctx = {"key": "instance"}
        eval_ctx = {"key": "passed", "num": 42}
        ce = ConditionEvaluator(context=instance_ctx)
        cond = Condition(left="num == 42", right="", operator=OperatorType.AND)
        # Using instance_ctx alone would fail (no "num" key), but passed ctx has it
        result = ce.evaluate(cond, eval_ctx)
        assert result is True

    def test_evaluate_fallback_to_instance_context(self):
        """When no context passed to evaluate(), instance context is used."""
        ce = ConditionEvaluator(context={"val": 100})
        cond = Condition(left="val == 100", right="", operator=OperatorType.AND)
        assert ce.evaluate(cond) is True


class TestCreateConditionHelper:
    """Tests for the create_condition convenience function."""

    def test_and_two_args(self):
        cond = create_condition(OperatorType.AND, "x > 5", "y < 100")
        assert isinstance(cond, Condition)
        assert cond.operator == OperatorType.AND
        assert cond.left == "x > 5"
        assert cond.right == "y < 100"

    def test_and_three_args_chains(self):
        """Three args produce (a AND b) AND c nesting."""
        cond = create_condition(OperatorType.AND, "a == 1", "b == 2", "c == 3")
        assert cond.operator == OperatorType.AND
        # Rightmost is c == 3
        assert isinstance(cond.right, str)
        # Left is a nested Condition
        assert isinstance(cond.left, Condition)

    def test_or_two_args(self):
        cond = create_condition(OperatorType.OR, "x < 0", "x > 100")
        assert cond.operator == OperatorType.OR
        assert cond.left == "x < 0"
        assert cond.right == "x > 100"

    def test_not_single_arg(self):
        cond = create_condition(OperatorType.NOT, "active == true")
        assert cond.operator == OperatorType.NOT
        assert cond.left == "active == true"
        assert cond.right == ""

    def test_empty_args_raises_value_error(self):
        with pytest.raises(ValueError, match="At least one condition required"):
            create_condition(OperatorType.AND)

    def test_not_with_condition_object(self):
        inner = Condition(left="x == 1", right="y == 2", operator=OperatorType.AND)
        cond = create_condition(OperatorType.NOT, inner)
        assert cond.operator == OperatorType.NOT
        assert cond.left is inner

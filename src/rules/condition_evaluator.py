"""条件评估器"""

import operator
import re
from typing import Any

from loguru import logger

from .advanced_models import Condition, OperatorType


class ConditionEvaluator:
    """条件评估器 - 支持AND/OR/NOT操作符的条件组合"""

    def __init__(self, context: dict[str, Any] | None = None):
        self.context = context or {}
        self._operators = {
            "==": operator.eq,
            "!=": operator.ne,
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "contains": lambda a, b: str(b) in str(a),
            "not_contains": lambda a, b: str(b) not in str(a),
            "matches": lambda a, b: bool(re.search(str(b), str(a))),
            "in": lambda a, b: a in b,
            "not_in": lambda a, b: a not in b,
            "starts_with": lambda a, b: str(a).startswith(str(b)),
            "ends_with": lambda a, b: str(a).endswith(str(b)),
            "exists": lambda a, _: a is not None,
            "is_empty": lambda a, _: not a,
        }

    def evaluate(
        self, condition: Condition, context: dict[str, Any] | None = None
    ) -> bool:
        """
        评估条件

        Args:
            condition: 要评估的条件
            context: 上下文数据

        Returns:
            条件是否满足
        """
        ctx = context or self.context

        if condition.operator == OperatorType.NOT:
            if isinstance(condition.left, Condition):
                return not self.evaluate(condition.left, ctx)
            return not self._evaluate_atomic(str(condition.left), ctx)

        left_result = (
            self.evaluate(condition.left, ctx)
            if isinstance(condition.left, Condition)
            else self._evaluate_atomic(str(condition.left), ctx)
        )

        if condition.operator == OperatorType.AND:
            if not left_result:
                return False
            if isinstance(condition.right, Condition):
                return self.evaluate(condition.right, ctx)
            return self._evaluate_atomic(str(condition.right), ctx)

        if condition.operator == OperatorType.OR:
            if left_result:
                return True
            if isinstance(condition.right, Condition):
                return self.evaluate(condition.right, ctx)
            return self._evaluate_atomic(str(condition.right), ctx)

        return False

    def _evaluate_atomic(self, expression: str, context: dict[str, Any]) -> bool:
        """
        评估原子条件表达式

        支持格式:
        - "key == value"
        - "key contains 'substring'"
        - "key matches 'pattern'"
        """
        try:
            expression = expression.strip()
            if not expression:
                return True

            for op_str, op_func in self._operators.items():
                op_pos = expression.find(op_str)
                if op_pos == -1:
                    continue

                left_part = expression[:op_pos].strip()
                right_part = expression[op_pos + len(op_str) :].strip()

                left_value = self._get_value(left_part, context)
                right_value = self._parse_value(right_part)

                return bool(op_func(left_value, right_value))

            if expression in context:
                return bool(context[expression])

            return True
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{expression}': {e}")
            return False

    def _get_value(self, key: str, context: dict[str, Any]) -> Any:
        """从上下文中获取值"""
        if not context:
            return None

        keys = key.split(".")
        value: Any = context

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                return None

        return value

    def _parse_value(self, value_str: str) -> Any:
        """解析值字符串"""
        value_str = value_str.strip()

        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False
        if value_str.lower() == "null" or value_str.lower() == "none":
            return None

        if (value_str.startswith('"') and value_str.endswith('"')) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]

        try:
            return int(value_str)
        except ValueError:
            pass

        try:
            return float(value_str)
        except ValueError:
            pass

        if value_str.startswith("[") and value_str.endswith("]"):
            try:
                import json

                return json.loads(value_str)
            except Exception:
                pass

        return value_str


def create_condition(operator: OperatorType, *conditions: str | Condition) -> Condition:
    """
    便捷创建条件

    Args:
        operator: 操作符
        *conditions: 条件列表

    Returns:
        组合条件
    """
    if not conditions:
        raise ValueError("At least one condition required")

    if operator == OperatorType.NOT:
        return Condition(left=conditions[0], right="", operator=operator)

    result = Condition(left=conditions[0], right=conditions[1], operator=operator)
    for cond in conditions[2:]:
        result = Condition(left=result, right=cond, operator=operator)

    return result

"""违规检测器 - 检测故障单是否涉及规范违规"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.core.models import ViolationDetection

if TYPE_CHECKING:
    from src.knowledge.manager import StandardsManager

VIOLATION_PATTERNS: dict[str, dict[str, str]] = {
    "empty_catch": {
        "pattern": r"catch\s*\([^)]+\)\s*\{\s*\}",
        "category": "java_coding",
        "subcategory": "异常处理",
        "description": "捕获异常后不做任何处理",
    },
    "database_connection_leak": {
        "pattern": r"(Connection|Statement|ResultSet|PreparedStatement).*getConnection\(\)",
        "category": "java_coding",
        "subcategory": "资源管理",
        "description": "数据库连接未关闭",
    },
    "non_thread_safe_collection": {
        "pattern": r"(new\s+)?(HashMap|ArrayList|HashSet)<",
        "category": "java_coding",
        "subcategory": "并发编程",
        "description": "多线程环境下使用非线程安全集合",
    },
    "system_out_println": {
        "pattern": r"System\.(out|err)\.(print|println)",
        "category": "java_coding",
        "subcategory": "日志规范",
        "description": "使用System.out输出日志",
    },
    "sql_injection": {
        "pattern": r"(executeQuery|execute|exec)\s*\(\s*[\"'].*\+",
        "category": "security",
        "subcategory": "SQL安全",
        "description": "存在SQL注入风险",
    },
    "function_in_index": {
        "pattern": r"WHERE\s+\w+\s*\([^)]+\)\s*(=|>|<|LIKE)",
        "category": "database_design",
        "subcategory": "索引设计",
        "description": "在索引列上使用函数",
    },
}


class ViolationDetector:
    """违规检测器 - 基于规范知识库检测故障是否涉及违规"""

    def __init__(self, standards_manager: StandardsManager) -> None:
        self._standards_manager = standards_manager
        self._violation_patterns = VIOLATION_PATTERNS

    def detect(self, fault_info: dict[str, Any]) -> ViolationDetection:
        """检测故障是否涉及违规

        Args:
            fault_info: 故障信息字典，包含task_id, title, description, code_snippet等

        Returns:
            ViolationDetection: 违规检测结果
        """
        code_snippet = fault_info.get("code_snippet", "")
        description = fault_info.get("description", "")
        title = fault_info.get("title", "")

        combined_text = f"{title} {description} {code_snippet}"

        violated_rules: list[str] = []
        violation_types: list[str] = []
        violation_categories: list[str] = []
        evidences: list[str] = []

        for violation_name, pattern_info in self._violation_patterns.items():
            pattern = pattern_info["pattern"]
            if re.search(pattern, code_snippet, re.IGNORECASE | re.MULTILINE):
                violated_rules.append(violation_name)
                violation_types.append(pattern_info["description"])
                violation_categories.append(pattern_info["category"])
                evidences.append(f"代码中检测到违规模式: {pattern_info['description']}")

        related_standards = self._find_related_standards(combined_text)

        is_violation = len(violated_rules) > 0

        confidence = self._calculate_confidence(is_violation, code_snippet, related_standards)

        return ViolationDetection(
            is_violation=is_violation,
            violation_type=violation_types[0] if violation_types else None,
            violation_category=violation_categories[0] if violation_categories else None,
            violated_rules=violated_rules,
            evidence="\n".join(evidences) if evidences else "",
            confidence=confidence,
            relevant_standards=related_standards,
        )

    def _find_related_standards(self, text: str) -> list[str]:
        """查找相关规范"""
        text_lower = text.lower()
        related = []

        for category in self._standards_manager.get_all_categories():
            for rule in category.rules:
                if (
                    rule.title.lower() in text_lower
                    or rule.subcategory.lower() in text_lower
                    or any(keyword in text_lower for keyword in rule.content.lower().split()[:5])
                ):
                    related.append(rule.id)

        return related[:5]

    def _calculate_confidence(
        self, is_violation: bool, code_snippet: str, related_standards: list[str]
    ) -> float:
        """计算违规置信度"""
        if not is_violation:
            if not code_snippet:
                return 0.0
            return 0.3

        confidence = 0.5

        if len(code_snippet) > 10:
            confidence += 0.2

        if len(related_standards) > 0:
            confidence += 0.2

        if len(code_snippet) > 50:
            confidence += 0.1

        return min(confidence, 1.0)

    def detect_by_llm(self, fault_info: dict[str, Any], llm_provider: Any) -> ViolationDetection:
        """使用LLM进行更深入的违规检测

        Args:
            fault_info: 故障信息字典
            llm_provider: LLM提供商实例

        Returns:
            ViolationDetection: 违规检测结果
        """
        prompt = self._build_llm_prompt(fault_info)

        try:
            response = llm_provider.generate(prompt)
            return self._parse_llm_response(response, fault_info)
        except Exception as e:
            logger.error(f"LLM违规检测失败: {e}")
            return self.detect(fault_info)

    def _build_llm_prompt(self, fault_info: dict[str, Any]) -> str:
        """构建LLM违规检测提示词"""
        categories = self._standards_manager.get_all_categories()

        standards_text = ""
        for cat in categories:
            standards_text += f"\n## {cat.name}\n"
            for rule in cat.rules[:5]:
                standards_text += f"- {rule.id}: {rule.title} ({rule.level})\n"

        return f"""你是一个代码规范审查专家。请分析以下故障是否涉及违规。

## 故障信息
- 标题: {fault_info.get("title", "")}
- 描述: {fault_info.get("description", "")}
- 代码片段:
```
{fault_info.get("code_snippet", "无")}
```

## 可用规范
{standards_text}

请分析并返回JSON格式的违规检测结果:
{{
    "is_violation": true/false,
    "violation_type": "违规类型描述",
    "violation_category": "违规类别",
    "violated_rules": ["规则ID列表"],
    "evidence": "违规证据",
    "confidence": 0.0-1.0,
    "relevant_standards": ["相关规范ID"]
}}
"""

    def _parse_llm_response(self, response: str, fault_info: dict[str, Any]) -> ViolationDetection:
        """解析LLM响应"""
        import json

        try:
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ViolationDetection(
                    is_violation=data.get("is_violation", False),
                    violation_type=data.get("violation_type"),
                    violation_category=data.get("violation_category"),
                    violated_rules=data.get("violated_rules", []),
                    evidence=data.get("evidence", ""),
                    confidence=data.get("confidence", 0.5),
                    relevant_standards=data.get("relevant_standards", []),
                )
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")

        return self.detect(fault_info)

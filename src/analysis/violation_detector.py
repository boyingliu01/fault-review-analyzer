"""违规检测器 - 检测故障单是否涉及规范违规"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.core.models import ViolationDetection

if TYPE_CHECKING:
    from src.knowledge.manager import StandardsManager

VIOLATION_PATTERNS: dict[str, dict[str, Any]] = {
    # === Java编码规范 ===
    "empty_catch": {
        "pattern": r"catch\s*\([^)]+\)\s*\{\s*\}",
        "category": "java_coding",
        "subcategory": "异常处理",
        "description": "捕获异常后不做任何处理（J000066）",
        "rule_id": "J000066",
    },
    "print_stack_trace": {
        "pattern": r"\.printStackTrace\s*\(\)",
        "category": "java_coding",
        "subcategory": "异常处理",
        "description": "使用printStackTrace输出异常（应使用Logger）",
        "rule_id": "J000066",
    },
    "database_connection_leak": {
        "pattern": r"(Connection|Statement|ResultSet|PreparedStatement).*getConnection\(\)",
        "category": "java_coding",
        "subcategory": "资源管理",
        "description": "数据库连接未关闭（J000076）",
        "rule_id": "J000076",
    },
    "non_thread_safe_collection": {
        "pattern": r"(new\s+)?(HashMap|ArrayList|HashSet)<",
        # 集合创建本身不构成违规，只有处于多线程上下文时才违反 J000025；
        # 旧逻辑不看上下文导致大量单线程场景误报（修正前 16/181 单命中
        # 多数不可信）。context_pattern 命中才检测主 pattern。
        "context_pattern": (
            r"\b(Thread|Runnable|Callable|synchronized|Executors?Service?"
            r"|ThreadPoolExecutor|ThreadPoolTaskExecutor|newFixedThreadPool"
            r"|newCachedThreadPool|@Async|parallelStream|CompletableFuture"
            r"|ForkJoin|CountDownLatch|Semaphore|Atomic\w+"
            r"|ConcurrentHashMap|CopyOnWrite\w+|BlockingQueue)\b"
        ),
        "category": "java_coding",
        "subcategory": "并发处理",
        "description": "多线程环境下使用非线程安全集合（J000025）",
        "rule_id": "J000025",
    },
    "system_out_println": {
        "pattern": r"System\.(out|err)\.(print|println)",
        "category": "java_coding",
        "subcategory": "日志规约",
        "description": "使用System.out输出日志（J000080）",
        "rule_id": "J000080",
    },
    "static_simple_date_format": {
        "pattern": r"static\s+.*SimpleDateFormat\s+",
        "category": "java_coding",
        "subcategory": "并发处理",
        "description": "SimpleDateFormat定义为静态变量（线程不安全）",
        "rule_id": "J000025",
    },
    "string_concat_in_loop": {
        "pattern": r"(for|while)\s*\(.*\{[\s\S]*?\w+\s*\+=\s*[\"']",
        "category": "java_coding",
        "subcategory": "集合处理",
        "description": "循环中使用字符串拼接（应使用StringBuilder）",
        "rule_id": "J000010",
    },
    # === 安全编码规范 ===
    "sql_injection": {
        "pattern": r"(executeQuery|execute|exec)\s*\(\s*[\"'].*\+",
        "category": "security",
        "subcategory": "数据校验",
        "description": "存在SQL注入风险（SEC-J00002）",
        "rule_id": "SEC-J00002",
    },
    "sql_string_concat": {
        "pattern": r"[\"']\s*(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)\s.*[\"']\s*\+\s*\w+",
        "category": "security",
        "subcategory": "数据校验",
        "description": "SQL语句拼接用户输入（SEC-J00002）",
        "rule_id": "SEC-J00002",
    },
    "command_injection": {
        "pattern": r"Runtime\.getRuntime\(\)\.exec\s*\(\s*\w+",
        "category": "security",
        "subcategory": "数据校验",
        "description": "Runtime.exec使用变量参数（命令注入风险 SEC-J00006）",
        "rule_id": "SEC-J00006",
    },
    "path_traversal": {
        "pattern": r"new\s+File\s*\(\s*(request\.|getParameter|\w+Input|userInput)",
        "category": "security",
        "subcategory": "数据校验",
        "description": "文件路径使用不可信输入（目录遍历风险 SEC-J00007）",
        "rule_id": "SEC-J00007",
    },
    "sensitive_info_in_log": {
        "pattern": r"(log|logger|LOG|LOGGER)\.\w+\([^)]*(password|secret|token|credential|key|密码|口令)",
        "category": "security",
        "subcategory": "其他安全规则",
        "description": "日志中输出敏感信息（SEC-J00033）",
        "rule_id": "SEC-J00033",
    },
    "hardcoded_secret": {
        "pattern": r"(password|passwd|secret|api_?key|token)\s*=\s*[\"'][^\"']{3,}[\"']",
        "category": "security",
        "subcategory": "其他安全规则",
        "description": "硬编码敏感信息（SEC-J00036）",
        "rule_id": "SEC-J00036",
    },
    "weak_encryption": {
        # 双侧词边界；DES/DESede/RC4 仅匹配大写算法常量（历史缺陷：旧正则缺少
        # 词头 \\b 且全局 IGNORECASE，导致 JS 的 .includes() 词尾 "des" 误报，
        # 见故障单 11964851）；md5/sha1 允许大小写（JS 中常以小写出现）。
        "pattern": r"\b(DES|DESede|RC4)\b|\b[Mm][Dd]5\b|\b[Ss][Hh][Aa]-?1\b",
        "flags": re.MULTILINE,  # 大小写敏感（覆盖默认 IGNORECASE）
        "category": "security",
        "subcategory": "其他安全规则",
        "description": "使用弱加密算法（SEC-J00034）",
        "rule_id": "SEC-J00034",
    },
    "xml_injection": {
        "pattern": r"(DocumentBuilder|SAXParser|XMLReader).*\+.*request",
        "category": "security",
        "subcategory": "数据校验",
        "description": "XML拼接不可信数据（SEC-J00003）",
        "rule_id": "SEC-J00003",
    },
    "function_in_index": {
        "pattern": r"WHERE\s+\w+\s*\([^)]+\)\s*(=|>|<|LIKE)",
        "category": "database_design",
        "subcategory": "索引设计",
        "description": "在索引列上使用函数",
        "rule_id": "",
    },
    "exception_info_leak": {
        "pattern": r"(catch\s*\([^)]+\)\s*\{[\s\S]*?)(e\.getMessage\(\)|e\.toString\(\)).*?(response|result|return)",
        "category": "security",
        "subcategory": "异常行为",
        "description": "异常信息泄露给外部（SEC-J00010）",
        "rule_id": "SEC-J00010",
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
            flags = pattern_info.get("flags", re.IGNORECASE | re.MULTILINE)
            # 部分模式需要代码中存在特定上下文才成立（如非线程安全集合
            # 需要多线程特征），避免脱离语境的误报
            context_pattern = pattern_info.get("context_pattern")
            if context_pattern and not re.search(context_pattern, code_snippet, re.IGNORECASE):
                continue
            if re.search(pattern, code_snippet, flags):
                rule_id = pattern_info.get("rule_id", "")
                rule_label = f"{rule_id}:{violation_name}" if rule_id else violation_name
                violated_rules.append(rule_label)
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

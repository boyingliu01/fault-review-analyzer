"""违规检测器测试套件"""

import re

from src.analysis.violation_detector import ViolationDetector
from src.core.models import ViolationDetection


class TestViolationDetector:
    """违规检测器测试套件"""

    def test_detect_violation_empty_catch_block(self, violation_detector):
        """测试检测空catch块违规"""
        fault_info = {
            "task_id": "TASK-001",
            "title": "空指针异常导致服务崩溃",
            "description": "代码中存在空的catch块，捕获异常后未做任何处理",
            "code_snippet": "try { int a = 1/0; } catch (Exception e) { }",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_detect_violation_database_connection_leak(self, violation_detector):
        """测试检测数据库连接泄漏违规"""
        fault_info = {
            "task_id": "TASK-002",
            "title": "数据库连接未关闭导致连接池耗尽",
            "description": "获取数据库连接后未关闭",
            "code_snippet": "Connection conn = dataSource.getConnection(); // 使用后未关闭",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)
        assert result.is_violation is True

    def test_detect_no_violation(self, violation_detector):
        """测试无违规情况"""
        fault_info = {
            "task_id": "TASK-003",
            "title": "正常的业务逻辑错误",
            "description": "业务逻辑计算错误，非规范违规",
            "code_snippet": "int result = a + b; // 逻辑错误",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_detect_violation_with_code_change(self, violation_detector):
        """测试带代码变更的违规检测"""
        fault_info = {
            "task_id": "TASK-004",
            "title": "并发安全问题",
            "description": "多线程环境下使用非线程安全集合",
            "code_snippet": "Map<String, Object> cache = new HashMap<>();",
            "development": {
                "commits": [
                    {
                        "commit_id": "abc123",
                        "message": "添加缓存功能",
                        "diff": "-Map<String, Object> cache = new HashMap<>();\n+Map<String, Object> cache = new ConcurrentHashMap<>();",
                    }
                ]
            },
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_violation_detection_confidence_score(self, violation_detector):
        """测试违规置信度评分"""
        fault_info = {
            "task_id": "TASK-005",
            "title": "明显违规",
            "description": "代码中使用System.out.println",
            "code_snippet": 'System.out.println("debug info");',
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0

    def test_violation_category_mapping(self, violation_detector):
        """测试违规类别映射"""
        fault_info = {
            "task_id": "TASK-006",
            "title": "SQL注入风险",
            "description": "存在SQL注入风险",
            "code_snippet": 'String sql = "SELECT * FROM users WHERE id=" + userId;',
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        if result.is_violation:
            assert result.violation_category is not None

    def test_violation_evidence_extraction(self, violation_detector):
        """测试违规证据提取"""
        fault_info = {
            "task_id": "TASK-007",
            "title": "异常处理问题",
            "description": "捕获异常后未记录日志",
            "code_snippet": "try { ... } catch (Exception e) { }",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        if result.is_violation:
            assert len(result.evidence) > 0

    def test_detect_with_empty_code_snippet(self, violation_detector):
        """测试空代码片段的违规检测"""
        fault_info = {
            "task_id": "TASK-008",
            "title": "无法确定",
            "description": "无法确定是否违规",
            "code_snippet": "",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)
        assert result.confidence <= 0.5


class TestViolationDetectorRuleDetails:
    """锁定 2026-09 复核修正后的行为：SEC-J00033 词表收紧、
    rule_details 逐规则对齐、evidence 记录真实命中行。"""

    def _fault(self, code_snippet: str, task_id: str) -> dict:
        return {
            "task_id": task_id,
            "title": "日志敏感信息复核",
            "description": "验证敏感信息日志检测行为",
            "code_snippet": code_snippet,
            "development": {"commits": []},
        }

    def test_log_message_text_not_flagged(self, violation_detector):
        """日志消息文本中的裸词 token 不再命中（11807893 误报模式）。"""
        result = violation_detector.detect(
            self._fault('logger.debug("expire uc token start...");', "TASK-101")
        )
        assert "SEC-J00033:sensitive_info_in_log" not in result.violated_rules

    def test_cache_key_output_not_flagged(self, violation_detector):
        """缓存键输出不再命中：裸 key 已移出 SEC-J00033 词表。"""
        result = violation_detector.detect(
            self._fault('logger.debug("cache key: {}", cacheKey);', "TASK-102")
        )
        assert "SEC-J00033:sensitive_info_in_log" not in result.violated_rules

    def test_sensitive_word_in_string_literal_not_flagged(self, violation_detector):
        """字符串字面量内的敏感词（占位文本）不算命中，仅匹配参数标识符。"""
        result = violation_detector.detect(
            self._fault('logger.info("user token expired", userId);', "TASK-104")
        )
        assert "SEC-J00033:sensitive_info_in_log" not in result.violated_rules

    def test_log_sensitive_identifier_hit(self, violation_detector):
        """日志参数中的敏感词标识符（输出敏感变量）仍应命中且详情对齐。"""
        result = violation_detector.detect(
            self._fault('logger.info("token={}", token);', "TASK-103")
        )
        assert result.is_violation is True
        assert "SEC-J00033:sensitive_info_in_log" in result.violated_rules
        sec = [d for d in result.rule_details if d["rule_id"] == "SEC-J00033"]
        assert len(sec) == 1
        assert sec[0]["pattern_key"] == "sensitive_info_in_log"
        assert sec[0]["category"] == "security"
        assert sec[0]["evidence"] == ['logger.info("token={}", token);']

    def test_evidence_contains_real_hit_line(self, violation_detector):
        """evidence 记录真实命中行，不再是无从复核的占位文本。"""
        code = 'System.out.println("debug info");\nlogger.info("pwd=" + pwd);'
        result = violation_detector.detect(self._fault(code, "TASK-105"))
        assert result.is_violation is True
        assert "命中行:" in result.evidence
        assert 'logger.info("pwd=" + pwd);' in result.evidence
        assert "代码中检测到违规模式" not in result.evidence

    def test_rule_details_align_with_violated_rules(self, violation_detector):
        """多规则命中时 rule_details 与 violated_rules 一一对应。"""
        code = (
            "try { int a = 1/0; } catch (Exception e) { }\n"
            'System.out.println("debug");\n'
            'logger.info("password={}", password);'
        )
        result = violation_detector.detect(self._fault(code, "TASK-106"))
        assert result.is_violation is True
        labels = [d["rule_label"] for d in result.rule_details]
        assert sorted(labels) == sorted(result.violated_rules)
        sec = [d for d in result.rule_details if d["rule_id"] == "SEC-J00033"]
        assert sec and sec[0]["description"] == "日志中输出敏感信息（SEC-J00033）"
        assert any("password" in line for line in sec[0]["evidence"])

    def test_rule_details_empty_when_no_violation(self, violation_detector):
        """无违规时 rule_details 为空列表。"""
        result = violation_detector.detect(self._fault("int result = a + b;", "TASK-107"))
        assert result.is_violation is False
        assert result.rule_details == []

    def test_extract_hit_lines_returns_line_of_match(self):
        """_extract_hit_lines 提取命中所在完整行（而非整段文本）。"""
        code = "line1 = 1;\npassword = 'abc12345';\nline3 = 3;"
        lines = ViolationDetector._extract_hit_lines(r"password", code, re.IGNORECASE)
        assert lines == ["password = 'abc12345';"]

    def test_extract_hit_lines_dedup_and_limit(self):
        """_extract_hit_lines 去重且最多返回 limit 条。"""
        code = "token = 'a';\ntoken = 'a';\ntoken = 'b';\ntoken = 'c';"
        lines = ViolationDetector._extract_hit_lines(r"token", code, re.IGNORECASE, limit=2)
        assert len(lines) == 2
        assert lines[0] == "token = 'a';"

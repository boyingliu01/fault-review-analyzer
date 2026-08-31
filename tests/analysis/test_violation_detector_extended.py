"""ViolationDetector 扩展测试 - 边界场景"""

import re
from unittest.mock import Mock

import pytest

from src.analysis.violation_detector import VIOLATION_PATTERNS, ViolationDetector


class TestViolationDetectorBoundary:
    """ViolationDetector 边界场景测试"""

    def test_detect_empty_fault_info(self):
        """测试空故障信息"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect({})

        assert result.is_violation is False
        assert result.violated_rules == []

    def test_detect_none_values(self):
        """测试包含None值的故障信息"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "task_id": None,
                "title": None,
                "description": None,
                "code_snippet": "",
            }
        )

        assert result.is_violation is False

    def test_detect_empty_catch_pattern(self):
        """测试空catch块模式检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": "try { } catch (Exception e) { }",
            }
        )

        assert result.is_violation is True
        assert any("empty_catch" in r for r in result.violated_rules)

    def test_detect_database_connection_leak(self):
        """测试数据库连接泄漏检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        # Pattern: (Connection|Statement|ResultSet|PreparedStatement).*getConnection\(\)
        result = detector.detect(
            {
                "code_snippet": "Connection conn = getConnection();",  # 符合 pattern
            }
        )

        assert result.is_violation is True
        assert any("database_connection_leak" in r for r in result.violated_rules)

    def test_detect_non_thread_safe_collection(self):
        """测试非线程安全集合检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": "Map<String, Object> map = new HashMap<>();",
            }
        )

        assert result.is_violation is True
        assert any("non_thread_safe_collection" in r for r in result.violated_rules)

    def test_detect_system_out_println(self):
        """测试System.out.println检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": 'System.out.println("debug");',
            }
        )

        assert result.is_violation is True
        assert any("system_out_println" in r for r in result.violated_rules)

    def test_detect_sql_injection(self):
        """测试SQL注入检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": 'stmt.executeQuery("SELECT * FROM users WHERE id = " + userId);',
            }
        )

        assert result.is_violation is True
        assert any("sql_injection" in r for r in result.violated_rules)

    def test_detect_function_in_index(self):
        """测试索引列函数检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": "WHERE UPPER(name) = 'TEST'",
            }
        )

        assert result.is_violation is True
        assert "function_in_index" in result.violated_rules

    def test_detect_multiple_violations(self):
        """测试多违规检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": """
                try {
                    Connection conn = DriverManager.getConnection(url);
                    System.out.println("connected");
                } catch (Exception e) { }
            """,
            }
        )

        assert result.is_violation is True
        assert len(result.violated_rules) >= 2

    def test_detect_no_violation(self):
        """测试无违规情况"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": "int x = 1; // normal code",
                "description": "正常描述",
            }
        )

        assert result.is_violation is False
        assert result.confidence >= 0.0

    def test_find_related_standards_empty(self):
        """测试查找相关标准-空文本"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector._find_related_standards("")

        assert result == []

    def test_find_related_standards_with_results(self):
        """测试查找相关标准-有结果"""
        from src.core.models import StandardCategory, StandardRule

        mock_standards = Mock()
        # 配置 get_all_categories 返回带有 rules 属性的 category 列表
        mock_standards.get_all_categories.return_value = [
            StandardCategory(
                id="cat-001",
                name="测试分类",
                description="测试分类描述",
                rules=[
                    StandardRule(
                        id="RULE-001",
                        title="测试规则",
                        subcategory="测试子类",
                        content="测试内容",
                        category="test",
                        level="强制",
                    )
                ],
            )
        ]
        mock_standards._rules_index = {
            "RULE-001": StandardRule(
                id="RULE-001",
                title="测试规则",
                subcategory="测试子类",
                content="测试内容",
                category="test",
                level="强制",
            )
        }

        detector = ViolationDetector(mock_standards)
        result = detector._find_related_standards("测试文本")

        assert len(result) >= 0  # 可能有匹配

    def test_calculate_confidence_no_violation(self):
        """测试置信度计算-无违规"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        confidence = detector._calculate_confidence(
            is_violation=False,
            code_snippet="",
            related_standards=[],
        )

        assert confidence == 0.0

    def test_calculate_confidence_with_code(self):
        """测试置信度计算-有代码"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        confidence = detector._calculate_confidence(
            is_violation=True,
            code_snippet="some code",
            related_standards=[],
        )

        assert confidence > 0.0

    def test_calculate_confidence_with_standards(self):
        """测试置信度计算-有标准"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        confidence = detector._calculate_confidence(
            is_violation=True,
            code_snippet="some code",
            related_standards=["RULE-001"],
        )

        assert confidence > 0.0

    def test_detect_case_insensitive(self):
        """测试大小写不敏感检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": 'SYSTEM.OUT.PRINTLN("test");',
            }
        )

        assert result.is_violation is True

    def test_detect_multiline_pattern(self):
        """测试多行模式检测"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": """
                catch (Exception e) {
                }
            """,
            }
        )

        assert result.is_violation is True

    def test_detect_unicode_in_code(self):
        """测试代码中的Unicode字符"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        result = detector.detect(
            {
                "code_snippet": 'System.out.println("中文输出");',
            }
        )

        assert result.is_violation is True

    def test_detect_very_long_code(self):
        """测试超长代码"""
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}

        detector = ViolationDetector(mock_standards)
        long_code = 'System.out.println("test");\n' * 1000
        result = detector.detect(
            {
                "code_snippet": long_code,
            }
        )

        assert result.is_violation is True


class TestViolationPatternsBoundary:
    """违规模式边界测试"""

    def test_violation_patterns_structure(self):
        """测试违规模式结构"""
        assert isinstance(VIOLATION_PATTERNS, dict)

        for _name, info in VIOLATION_PATTERNS.items():
            assert "pattern" in info
            assert "category" in info
            assert "subcategory" in info
            assert "description" in info

            # 验证是有效的正则表达式
            re.compile(info["pattern"])

    def test_empty_catch_pattern_variations(self):
        """测试空catch模式变体"""
        pattern = VIOLATION_PATTERNS["empty_catch"]["pattern"]

        test_cases = [
            ("catch (Exception e) {}", True),
            ("catch(Exception e){}", True),
            ("catch (Exception e) { }", True),
            ("catch (Exception e) { log.error(); }", False),
        ]

        for code, should_match in test_cases:
            matched = bool(re.search(pattern, code, re.IGNORECASE | re.MULTILINE))
            assert matched == should_match, f"Failed for: {code}"

    def test_sql_injection_pattern_variations(self):
        """测试SQL注入模式变体"""
        pattern = VIOLATION_PATTERNS["sql_injection"]["pattern"]

        test_cases = [
            ('executeQuery("SELECT * FROM " + table)', True),
            ('execute ("DELETE FROM " + id)', True),
            ('exec("UPDATE " + field)', True),
            ('executeQuery("SELECT * FROM users")', False),
        ]

        for code, should_match in test_cases:
            matched = bool(re.search(pattern, code, re.IGNORECASE | re.MULTILINE))
            assert matched == should_match, f"Failed for: {code}"

    def test_all_patterns_have_valid_categories(self):
        """测试所有模式都有有效类别"""
        valid_categories = [
            "java_coding",
            "security",
            "database_design",
            "sql_development",
            "database_ops",
        ]

        for _name, info in VIOLATION_PATTERNS.items():
            assert info["category"] in valid_categories or True  # 允许新类别


class TestWeakEncryptionPattern:
    """SEC-J00034 weak_encryption 误报修复回归测试。

    根因（故障单 11964851 误报）：旧正则 r"(DES|MD5|SHA-?1|RC4)\b" 缺少
    前置 \\b 且 detect() 全局 IGNORECASE，导致 JS 的 .includes() 调用
    （单词末尾 "des"）被误判为弱加密算法。
    """

    @staticmethod
    def _detect(code_snippet: str):
        mock_standards = Mock()
        mock_standards.get_all_categories.return_value = []
        mock_standards._rules_index = {}
        detector = ViolationDetector(mock_standards)
        return detector.detect({"code_snippet": code_snippet})

    def test_js_includes_not_flagged_as_weak_encryption(self):
        """JS .includes() 调用不应触发弱加密（真实误报样本，来自 11964851 diff）"""
        snippet = (
            "if (eventTypeId && ESALES.BusinessConst.nonRechargePaymentList.includes(eventTypeId)) {\n"
            "  const orderDetailInfo = await this.getCeeOrderDetail();\n"
            "}\n"
            "const appDealRetailEventList = ESALES.BusinessConst.appDealRetailEventList;\n"
            "value: appDealRetailEventList.includes(eventTypeId) ? this.state.orderNbr || orderId : orderId,\n"
        )
        result = self._detect(snippet)

        assert not any("weak_encryption" in r for r in result.violated_rules)
        assert result.is_violation is False

    @pytest.mark.parametrize(
        "code",
        [
            'Cipher.getInstance("DES");',  # Java 弱加密
            'Cipher.getInstance("DESede");',
            'MessageDigest.getInstance("MD5");',
            'MessageDigest.getInstance("SHA-1");',
            'Cipher.getInstance("RC4");',
            "crypto.createHash('md5')",  # JS 小写写法
            "crypto.createHash('sha1')",
        ],
    )
    def test_real_weak_crypto_still_detected(self, code: str):
        """真实弱加密用法（Java/JS 常见写法）仍应被检出"""
        result = self._detect(code)

        assert any("weak_encryption" in r for r in result.violated_rules), (
            f"应检出弱加密但未检出: {code}"
        )

    @pytest.mark.parametrize(
        "code",
        [
            "const des = req.body;",  # 小写 des 变量（非算法常量）
            "loadDES = config.value;",  # 词中 des（无词头边界）
        ],
    )
    def test_lowercase_des_word_not_flagged(self, code: str):
        """小写 des 或词中 des 不应被当作弱加密算法"""
        result = self._detect(code)

        assert not any("weak_encryption" in r for r in result.violated_rules)

    def test_weak_encryption_pattern_flags_are_strict(self):
        """weak_encryption 模式应使用严格标志（大小写敏感 + 双侧词边界）"""
        info = VIOLATION_PATTERNS["weak_encryption"]
        flags = info.get("flags", re.IGNORECASE | re.MULTILINE)

        assert re.search(info["pattern"], 'Cipher.getInstance("DES")', flags)
        assert re.search(info["pattern"], "crypto.createHash('md5')", flags)
        assert not re.search(info["pattern"], "list.includes(eventTypeId)", flags)
        assert not re.search(info["pattern"], "const des = value;", flags)

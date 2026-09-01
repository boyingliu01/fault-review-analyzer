"""security-001 误报修复回归测试（A2/A7 修复）。

旧正则含裸词 key|token，IGNORECASE 下 cacheKey/KEY 等普通变量名大量
误报（修正前 41/181 单命中，证据全为变量名，如 11964009 的
['KEY','key','KEY','Key','key']）；且 findall 带分组时 evidence 沦为
分组元组，无法复核。本文件锁定修复后的行为。
"""

from src.rules.engine import RulesEngine


class TestSecurity001Regex:
    def _check(self, code: str):
        engine = RulesEngine()
        return engine.check({"development": {"commits": [{"message": "", "diff": code}]}})

    def test_hardcoded_password_still_detected(self):
        """硬编码密码仍应检出（e2e fixture 同款裸代码 diff 形式）"""
        violations = self._check("PASSWORD = 'test123'  # hardcoded credential")
        assert any(v.rule_id == "security-001" for v in violations)

    def test_commit_message_password_detected(self):
        """无 diff 降级到 commit message 的场景仍应检出"""
        engine = RulesEngine()
        violations = engine.check(
            {"development": {"commits": [{"message": "password='secret'"}]}}
        )
        assert any(v.rule_id == "security-001" for v in violations)

    def test_bare_key_variable_not_flagged(self):
        """裸 key/cacheKey 变量名不再误报"""
        violations = self._check('key = "KEY"\ncacheKey = "abc12345"')
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_short_placeholder_value_not_flagged(self):
        """短占位符值（<6字符）不报"""
        violations = self._check('token = "abc"')
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_jwt_token_still_detected(self):
        """认证令牌硬编码仍应检出"""
        violations = self._check('var token = "eyJhbGciOiJIUzI1NiJ9";')
        assert any(v.rule_id == "security-001" for v in violations)

    def test_deleted_lines_not_flagged(self):
        """diff 删除行中的违规不应报（A1：被删除代码不是本次引入）"""
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-password = 'OldSecret123'\n"
            " clean_line = 1\n"
            "+safe_value = compute()\n"
        )
        violations = self._check(diff)
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_added_lines_still_flagged(self):
        """diff 新增行中的违规应正常报出"""
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,2 +1,3 @@\n"
            " clean_line = 1\n"
            "+password = 'NewSecret99'\n"
        )
        violations = self._check(diff)
        assert any(v.rule_id == "security-001" for v in violations)

    def test_evidence_is_code_line_not_group_tuple(self):
        """evidence 应为完整代码行而非分组元组（A2 evidence 修复）"""
        violations = self._check("password = 'supersecret'")
        sec = [v for v in violations if v.rule_id == "security-001"]
        assert sec
        assert sec[0].evidence
        assert "password" in sec[0].evidence[0]

    def test_rule_flags_respected(self):
        """规则级 flags 生效：security-001 保持 IGNORECASE"""
        engine = RulesEngine()
        rule = engine.get_rule("security-001")
        assert rule is not None
        assert rule.flags & 2  # re.IGNORECASE == 2

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
        violations = engine.check({"development": {"commits": [{"message": "password='secret'"}]}})
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


class TestSecurity001Recheck202609:
    """2026-09 复核修正锁定：181 单中 12 条敏感信息认定经逐条人工复核
    全为误报（配置键常量/跨引号假阳性/校验规则/mock 测试数据），规则据此
    收紧。本类锁定新误报模式不再命中、真实凭证仍检出。"""

    def _check(self, code: str):
        engine = RulesEngine()
        return engine.check({"development": {"commits": [{"message": "", "diff": code}]}})

    def test_config_key_constant_not_flagged(self):
        """配置键常量定义不报：值是配置键路径而非凭证（11797805/11797806）"""
        code = (
            'public static final String PWD_EXPIRE_DAYS = "ecare.user.pwd.expire-days";\n'
            'public static final String PWD_DIFFER_PREVIOUS_COUNT = "ecare.mod-pwd.pwd-differ-previous-count";\n'
            'public static final String TOKEN_AUTO_KICK_OUT = "webs.ecare.token.auto-kick-out";\n'
            'public static final String APP_SECRET = "uc.appSecret";'
        )
        violations = self._check(code)
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_string_concat_token_not_flagged(self):
        """URL 拼接变量值不报：token 值来自 getNaireToken() 变量（11857576）"""
        code = (
            '.append(questionNaireLanguage).append("&token=")'
            '.append(mccContact.getNaireToken()).append("&")'
        )
        violations = self._check(code)
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_validation_rule_expression_not_flagged(self):
        """表单校验规则声明不报（11862289）"""
        violations = self._check("pwd: 'required(reservePwdRequiredRule);'")
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_variable_assignment_not_flagged(self):
        """变量赋值/注释中的 token 词不报（11937118）"""
        code = (
            '// LogUtils.d("SdkDxpBaseModule", "token :" + token)\n'
            "CEEUserInfoManage.getInstance().token = token\n"
            "clearSensitiveUserInfoCache()"
        )
        violations = self._check(code)
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_test_file_mock_token_not_flagged(self):
        """测试文件中的 mock token 不报：文件级跳过（11964009 __tests__）"""
        diff = (
            "diff --git a/src/deeplink/__tests__/DeepLink.test.js "
            "b/src/deeplink/__tests__/DeepLink.test.js\n"
            "--- a/src/deeplink/__tests__/DeepLink.test.js\n"
            "+++ b/src/deeplink/__tests__/DeepLink.test.js\n"
            "@@ -1,1 +1,2 @@\n"
            "+      getState: () => ({ UserInfo: { userData: { token: 'tok-b8' } } }),\n"
        )
        violations = self._check(diff)
        assert not any(v.rule_id == "security-001" for v in violations)

    def test_mock_token_in_production_file_still_flagged(self):
        """生产文件中的同形 mock 值仍应报出（不因值形态漏报）"""
        violations = self._check("getState: () => ({ token: 'tok-b8' }),")
        assert any(v.rule_id == "security-001" for v in violations)

    def test_dotted_jwt_still_detected(self):
        """带点的 JWT 硬编码仍应检出（eyJ 前缀不受点分键排除影响）"""
        code = (
            "var token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';"
        )
        violations = self._check(code)
        assert any(v.rule_id == "security-001" for v in violations)

    def test_real_credentials_still_detected(self):
        """真实凭证形态仍应检出（不因收紧漏报）。

        engine 按规则聚合产出一条 RuleViolation，多条命中全部进入
        evidence——断言三条凭证（含冒号形态 authToken 与超长 token 值）
        逐一被捕获，锁定不漏报。
        """
        code = (
            "api_key = 'sk-abcdef1234567890'\n"
            "password = 'SuperSecret123'\n"
            "authToken: 'ghp_16C7e42F292c6912E7710c838347Ae178B4a'"
        )
        violations = self._check(code)
        sec = [v for v in violations if v.rule_id == "security-001"]
        assert len(sec) == 1
        evidence_lines = sec[0].evidence
        assert any("sk-abcdef1234567890" in line for line in evidence_lines)
        assert any("SuperSecret123" in line for line in evidence_lines)
        assert any("ghp_16C7e42F292c6912E7710c838347Ae178B4a" in line for line in evidence_lines)

    def test_value_exclude_options_wired(self):
        """security-001 的 value_exclude 选项已装配到规则"""
        engine = RulesEngine()
        rule = engine.get_rule("security-001")
        assert rule is not None
        assert rule.options.get("value_group") == 2
        assert "eyJ" in str(rule.options.get("value_exclude"))

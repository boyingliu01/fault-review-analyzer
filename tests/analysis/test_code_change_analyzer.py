"""代码变更分析器测试套件"""

from datetime import datetime

from src.core.models import CodeChange


class TestCodeChangeAnalyzer:
    """代码变更分析器测试套件"""

    def test_parse_commit_list(self, code_change_analyzer):
        """测试解析commit列表"""
        commits = [
            {
                "commit_id": "abc123",
                "message": "添加用户认证功能",
                "author": "developer1",
                "timestamp": "2024-01-15T10:00:00",
                "files_changed": ["src/auth.py", "src/models.py"],
            },
            {
                "commit_id": "def456",
                "message": "修复登录bug",
                "author": "developer1",
                "timestamp": "2024-01-15T11:00:00",
                "files_changed": ["src/auth.py"],
            },
        ]
        result = code_change_analyzer.parse_commits(commits)
        assert len(result) == 2
        assert isinstance(result[0], CodeChange)

    def test_analyze_diff(self, code_change_analyzer):
        """测试分析代码diff"""
        diff = """--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,8 @@
+import logging
+log = logging.getLogger(__name__)
-
-def authenticate(user):
+def authenticate(user, password):
     return user.is_authenticated()
"""
        result = code_change_analyzer.analyze_diff(diff)
        assert "added_lines" in result
        assert "removed_lines" in result

    def test_detect_file_types(self, code_change_analyzer):
        """测试文件类型检测"""
        files = ["src/auth.py", "src/service.go", "src/utils.js", "src/config.xml"]
        result = code_change_analyzer.detect_file_types(files)
        assert result.get("src/auth.py") == "python"
        assert result.get("src/service.go") == "go"
        assert result.get("src/utils.js") == "javascript"

    def test_identify_changed_modules(self, code_change_analyzer):
        """测试识别变更模块"""
        files = [
            "src/auth/login.py",
            "src/auth/logout.py",
            "src/user/profile.py",
            "tests/test_auth.py",
        ]
        result = code_change_analyzer.identify_changed_modules(files)
        assert "src/auth" in result
        assert "src/user" in result

    def test_generate_change_summary(self, code_change_analyzer):
        """测试生成变更摘要"""
        code_changes = [
            CodeChange(
                commit_id="abc123",
                author="dev1",
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                message="添加登录功能",
                diff="+def login(): pass",
                files_changed=["src/login.py"],
                branch="main",
                repository="app",
            )
        ]
        summary = code_change_analyzer.generate_change_summary(code_changes)
        assert "total_commits" in summary
        assert summary["total_commits"] == 1

    def test_empty_commits(self, code_change_analyzer):
        """测试空commit列表"""
        result = code_change_analyzer.parse_commits([])
        assert len(result) == 0

    def test_extract_code_patterns(self, code_change_analyzer):
        """测试提取代码模式"""
        diff = """+try {
+    connection = dataSource.getConnection();
+} catch (SQLException e) {
+    log.error(e);
+}"""
        patterns = code_change_analyzer.extract_code_patterns(diff)
        assert len(patterns) > 0

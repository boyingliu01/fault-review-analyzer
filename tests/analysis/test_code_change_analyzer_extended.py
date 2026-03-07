"""CodeChangeAnalyzer 扩展测试 - 边界场景"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.analysis.code_change_analyzer import CodeChangeAnalyzer, FILE_TYPE_MAP, CODE_PATTERNS
from src.core.models import CodeChange


class TestCodeChangeAnalyzerBoundary:
    """CodeChangeAnalyzer 边界场景测试"""

    def test_parse_commits_empty_list(self):
        """测试空commit列表"""
        analyzer = CodeChangeAnalyzer()
        result = analyzer.parse_commits([])
        assert result == []

    def test_parse_commits_none_values(self):
        """测试包含None值的commit - Pydantic验证失败会跳过"""
        analyzer = CodeChangeAnalyzer()
        commits = [
            {
                "commit_id": None,
                "author": None,
                "timestamp": None,
                "message": None,
                "files_changed": None,
                "diff": None,
            }
        ]
        # Pydantic 验证失败时，parse_commits 会跳过该 commit
        result = analyzer.parse_commits(commits)
        # 由于验证失败，返回空列表
        assert len(result) == 0

    def test_parse_commits_invalid_timestamp(self):
        """测试无效时间戳"""
        analyzer = CodeChangeAnalyzer()
        commits = [
            {
                "commit_id": "abc123",
                "author": "test",
                "timestamp": "invalid-timestamp",
                "message": "test",
            }
        ]
        result = analyzer.parse_commits(commits)
        assert len(result) == 1
        assert isinstance(result[0].timestamp, datetime)

    def test_parse_commits_datetime_object(self):
        """测试datetime对象作为timestamp"""
        analyzer = CodeChangeAnalyzer()
        now = datetime.now()
        commits = [
            {
                "commit_id": "abc123",
                "author": "test",
                "timestamp": now,
                "message": "test",
            }
        ]
        result = analyzer.parse_commits(commits)
        assert result[0].timestamp == now

    def test_parse_commits_missing_fields(self):
        """测试缺少字段的commit"""
        analyzer = CodeChangeAnalyzer()
        commits = [{}]
        result = analyzer.parse_commits(commits)
        assert len(result) == 1
        assert result[0].commit_id == ""
        assert result[0].author == ""

    def test_detect_file_types_empty(self):
        """测试空文件列表"""
        analyzer = CodeChangeAnalyzer()
        result = analyzer.detect_file_types([])
        assert result == {}

    def test_detect_file_types_unknown_extension(self):
        """测试未知文件扩展名"""
        analyzer = CodeChangeAnalyzer()
        files = ["file.unknown", "another.xyz"]
        result = analyzer.detect_file_types(files)
        assert result.get("file.unknown") == "unknown"
        assert result.get("another.xyz") == "unknown"

    def test_detect_file_types_no_extension(self):
        """测试无扩展名的文件"""
        analyzer = CodeChangeAnalyzer()
        files = ["Makefile", "Dockerfile", ".gitignore"]
        result = analyzer.detect_file_types(files)
        assert result.get("Makefile") == "unknown"
        assert result.get("Dockerfile") == "unknown"

    def test_detect_file_types_mixed_case(self):
        """测试大小写混合的扩展名"""
        analyzer = CodeChangeAnalyzer()
        files = ["test.PY", "test.JAVA", "test.JS"]
        result = analyzer.detect_file_types(files)
        # 应该能识别大小写不敏感的扩展名
        assert "test.PY" in result

    def test_analyze_diff_empty(self):
        """测试空diff内容"""
        analyzer = CodeChangeAnalyzer()
        result = analyzer.analyze_diff("")
        assert result["added_lines"] == 0
        assert result["removed_lines"] == 0

    def test_analyze_diff_none(self):
        """测试None diff内容"""
        analyzer = CodeChangeAnalyzer()
        result = analyzer.analyze_diff(None)
        assert result["added_lines"] == 0
        assert result["removed_lines"] == 0

    def test_analyze_diff_with_changes(self):
        """测试有变更的diff"""
        analyzer = CodeChangeAnalyzer()
        diff = """
+ added line 1
+ added line 2
- removed line 1
+++ b/test.py
--- a/test.py
"""
        result = analyzer.analyze_diff(diff)
        assert result["added_lines"] == 2
        assert result["removed_lines"] == 1
        assert result["modified_lines"] == 3

    def test_analyze_diff_multiple_files(self):
        """测试多文件diff"""
        analyzer = CodeChangeAnalyzer()
        diff = """
+++ b/file1.py
--- a/file1.py
+ change 1
+++ b/file2.py
--- a/file2.py
+ change 2
"""
        result = analyzer.analyze_diff(diff)
        assert result["files_modified"] > 0

    def test_analyze_code_changes_empty(self):
        """测试空commits分析"""
        analyzer = CodeChangeAnalyzer()
        result = analyzer.analyze_code_changes([])
        assert "summary" in result
        assert result["summary"]["total_commits"] == 0

    def test_analyze_code_changes_single(self):
        """测试单commit分析"""
        analyzer = CodeChangeAnalyzer()
        commits = [
            {
                "commit_id": "abc123",
                "author": "test",
                "timestamp": "2024-01-01T00:00:00",
                "message": "fix bug",
                "files_changed": ["test.py"],
                "diff_content": "+ added line",
            }
        ]
        result = analyzer.analyze_code_changes(commits)
        assert result["summary"]["total_commits"] == 1
        assert len(result["summary"]["authors"]) == 1

    def test_analyze_code_changes_multiple(self):
        """测试多commits分析"""
        analyzer = CodeChangeAnalyzer()
        commits = [
            {
                "commit_id": f"abc{i}",
                "author": f"author{i % 3}",
                "timestamp": "2024-01-01T00:00:00",
                "message": f"commit {i}",
                "files_changed": [f"file{i}.py"],
                "diff_content": "+ change",
            }
            for i in range(10)
        ]
        result = analyzer.analyze_code_changes(commits)
        assert result["summary"]["total_commits"] == 10
        assert len(result["summary"]["authors"]) == 3

    def test_analyze_code_changes_with_stats(self):
        """测试带统计信息的commits分析"""
        analyzer = CodeChangeAnalyzer()
        commits = [
            {
                "commit_id": "abc",
                "author": "test",
                "timestamp": "2024-01-01T00:00:00",
                "message": "big change",
                "files_changed": ["file1.py", "file2.py"],
                "diff_content": "+ line1\n+ line2\n- line3",
            }
        ]
        result = analyzer.analyze_code_changes(commits)
        assert "diff_stats" in result
        assert result["summary"]["total_files_changed"] == 2


class TestCodePatternsBoundary:
    """代码模式边界测试"""

    def test_file_type_map_completeness(self):
        """测试文件类型映射完整性"""
        common_extensions = [
            ".py", ".java", ".js", ".ts", ".go", ".cpp", ".c", ".sql"
        ]
        for ext in common_extensions:
            assert ext in FILE_TYPE_MAP, f"Missing {ext} in FILE_TYPE_MAP"

    def test_code_patterns_structure(self):
        """测试代码模式结构"""
        assert isinstance(CODE_PATTERNS, dict)
        for category, patterns in CODE_PATTERNS.items():
            assert isinstance(category, str)
            assert isinstance(patterns, list)
            for pattern in patterns:
                assert isinstance(pattern, str)
                # 验证是有效的正则表达式
                import re
                re.compile(pattern)

    def test_code_patterns_database_connection(self):
        """测试数据库连接模式匹配"""
        import re
        test_cases = [
            ("Connection conn = getConnection();", True),
            ("Statement stmt = conn.createStatement();", True),
            ("random text", False),
        ]
        for text, should_match in test_cases:
            matched = any(
                re.search(pattern, text)
                for pattern in CODE_PATTERNS["database_connection"]
            )
            assert matched == should_match, f"Failed for: {text}"

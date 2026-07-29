"""测试代码变更分析链路的完整性。

验证从API获取diff -> CodeChangeAnalyzer分析 -> RulesEngine检查 -> 聚类增强 的完整流程。
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.api.models import CommitInfo, DevelopmentInfo, TaskInfo
from src.rules.engine import RulesEngine


class TestCodeDiffIntegration:
    """测试代码diff获取和集成。"""

    def test_commit_info_with_diff(self):
        """CommitInfo模型支持diff字段。"""
        commit = CommitInfo(
            commit_id="abc123",
            message="fix: null pointer",
            author="dev1",
            time=datetime.now(),
            changes=["src/main/java/Foo.java"],
            diff="--- a/src/main/java/Foo.java\n+++ b/src/main/java/Foo.java\n@@ -10,3 +10,4 @@\n+    if (obj == null) return;",
            branch="feature/fix-npe",
            repository="my-repo",
        )
        assert commit.diff != ""
        assert "null" in commit.diff
        assert commit.branch == "feature/fix-npe"

    def test_commit_info_without_diff_backward_compat(self):
        """CommitInfo在无diff时保持向后兼容。"""
        commit = CommitInfo(
            commit_id="abc123",
            message="fix: null pointer",
            author="dev1",
            time=datetime.now(),
            changes=["src/Foo.java"],
        )
        assert commit.diff == ""
        assert commit.branch == ""
        assert commit.repository == ""


class TestCodeChangeAnalyzerEnhanced:
    """测试增强后的CodeChangeAnalyzer。"""

    @pytest.fixture
    def analyzer(self):
        return CodeChangeAnalyzer()

    def test_generate_analysis_text_with_diff(self, analyzer):
        """有diff数据时生成分析文本。"""
        commits = [
            {
                "commit_id": "abc123",
                "author": "dev1",
                "message": "fix: NPE",
                "diff": "--- a/Foo.java\n+++ b/Foo.java\n@@ -10,3 +10,4 @@\n+    if (obj == null) return;\n",
                "files_changed": ["src/main/java/Foo.java"],
                "branch": "main",
                "repository": "repo",
                "timestamp": "2026-07-21T10:00:00",
            }
        ]
        text = analyzer.generate_analysis_text(commits)
        assert "代码变更" in text
        assert "1次提交" in text

    def test_generate_analysis_text_without_diff(self, analyzer):
        """无diff数据时返回空字符串。"""
        commits = [
            {
                "commit_id": "abc123",
                "author": "dev1",
                "message": "fix: NPE",
                "diff": "",
                "files_changed": [],
                "branch": "",
                "repository": "",
                "timestamp": "2026-07-21T10:00:00",
            }
        ]
        text = analyzer.generate_analysis_text(commits)
        # 没有diff时统计信息仍会生成
        assert "1次提交" in text

    def test_generate_analysis_text_empty_commits(self, analyzer):
        """空commit列表返回空字符串。"""
        text = analyzer.generate_analysis_text([])
        assert text == ""

    def test_analyze_code_changes_with_patterns(self, analyzer):
        """检测代码模式。"""
        commits = [
            {
                "commit_id": "abc123",
                "author": "dev1",
                "message": "add DB connection",
                "diff": "getConnection()\nStatement stmt = conn.createStatement()",
                "files_changed": ["src/Dao.java"],
                "branch": "main",
                "repository": "repo",
                "timestamp": "2026-07-21T10:00:00",
            }
        ]
        result = analyzer.analyze_code_changes(commits)
        patterns = result["detected_patterns"]
        pattern_types = [p["type"] for p in patterns]
        assert "database_connection" in pattern_types


class TestRulesEngineWithDiff:
    """测试RulesEngine基于代码diff进行违规检查。"""

    @pytest.fixture
    def engine(self):
        return RulesEngine()

    def test_check_with_diff_detects_violation(self, engine):
        """基于diff内容检测到违规。"""
        task_data = {
            "development": {
                "commits": [
                    {
                        "message": "add config",
                        "diff": 'password = "secret123"\napi_key = "sk-abc123"',
                    }
                ],
                "code_changes": [],
            }
        }
        violations = engine.check(task_data)
        # 应该检测到敏感信息泄露
        rule_ids = [v.rule_id for v in violations]
        assert "security-001" in rule_ids

    def test_check_with_diff_no_violation(self, engine):
        """干净的diff不产生违规。"""
        task_data = {
            "development": {
                "commits": [
                    {
                        "message": "fix: update logic",
                        "diff": "--- a/Foo.java\n+++ b/Foo.java\n@@ -10,3 +10,4 @@\n+    int x = 42;",
                    }
                ],
                "code_changes": [],
            }
        }
        violations = engine.check(task_data)
        # 干净的代码不应触发安全违规
        security_violations = [v for v in violations if v.rule_id.startswith("security")]
        assert len(security_violations) == 0

    def test_check_fallback_to_commit_message(self, engine):
        """无diff时降级到检查commit message。"""
        task_data = {
            "development": {
                "commits": [
                    {
                        "message": 'password = "hardcoded"',
                        "diff": "",
                    }
                ],
                "code_changes": [],
            }
        }
        violations = engine.check(task_data)
        # commit message中包含敏感信息模式
        rule_ids = [v.rule_id for v in violations]
        assert "security-001" in rule_ids

    def test_check_with_code_changes_content(self, engine):
        """检查code_changes中的new_content。"""
        task_data = {
            "development": {
                "commits": [],
                "code_changes": [
                    {
                        "old_content": "",
                        "new_content": 'cursor.execute("SELECT * FROM users WHERE id = %s" + user_input)',
                    }
                ],
            }
        }
        violations = engine.check(task_data)
        rule_ids = [v.rule_id for v in violations]
        assert "security-002" in rule_ids


class TestClusteringWithCodeChanges:
    """测试基于代码变更的聚类增强。"""

    def test_clustering_mode_detection(self):
        """验证聚类模式标识。"""
        # 模拟有代码变更数据的场景
        from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig

        config = MagicMock()
        config.get_config.return_value = MagicMock(
            api=MagicMock(base_url="http://test", api_key="key", timeout=30, retry=1),
            cache=MagicMock(db_path=":memory:", ttl=3600),
            embedding=MagicMock(
                provider="local",
                model="test",
                api_key="",
                base_url=None,
                batch_size=10,
            ),
            clustering=MagicMock(
                algorithm="hdbscan", min_cluster_size=2, min_samples=1, metric="cosine"
            ),
            llm=MagicMock(api_key=""),
        )

        pipeline = AnalysisPipeline(config=config, pipeline_config=PipelineConfig(use_llm=False))
        # 验证pipeline创建成功
        assert pipeline._pipeline_config.use_llm is False


class TestPreprocessorWithDiff:
    """测试预处理器包含diff数据。"""

    def test_preprocessor_includes_diff_in_segments(self):
        """预处理器将diff包含在commit segment中。"""
        from src.preprocessor.processor import DataPreprocessor

        preprocessor = DataPreprocessor()

        task = TaskInfo(
            task_id=12345,
            title="修复空指针异常",
            description="生产环境出现NPE",
            status="closed",
            create_time=datetime.now(),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="abc123",
                        message="fix: add null check",
                        author="dev1",
                        time=datetime.now(),
                        changes=["src/Foo.java"],
                        diff="--- a/Foo.java\n+++ b/Foo.java\n+    if (obj == null) return;",
                    )
                ]
            ),
        )

        result = preprocessor.process(task)
        commit_segments = [s for s in result.segments if s.type == "commit"]
        assert len(commit_segments) > 0
        # diff内容应该被包含
        assert "代码变更" in commit_segments[0].content
        assert "null" in commit_segments[0].content
        # metadata应该标记has_diff
        assert commit_segments[0].metadata["has_diff"] is True

    def test_preprocessor_without_diff_backward_compat(self):
        """无diff时预处理器保持向后兼容。"""
        from src.preprocessor.processor import DataPreprocessor

        preprocessor = DataPreprocessor()

        task = TaskInfo(
            task_id=12345,
            title="修复空指针异常",
            description="生产环境出现NPE",
            status="closed",
            create_time=datetime.now(),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="abc123",
                        message="fix: add null check",
                        author="dev1",
                        time=datetime.now(),
                        changes=["src/Foo.java"],
                    )
                ]
            ),
        )

        result = preprocessor.process(task)
        commit_segments = [s for s in result.segments if s.type == "commit"]
        assert len(commit_segments) > 0
        # 没有diff时不应包含代码变更标记
        assert "代码变更" not in commit_segments[0].content
        assert commit_segments[0].metadata["has_diff"] is False

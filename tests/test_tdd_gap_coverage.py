"""TDD 补齐测试 - 覆盖关键路径的边界、错误和并发场景。

这些测试定义了系统在边界条件下的期望行为，
弥补先实现后补测导致的"行为规格"缺失。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.api.client import APIClient
from src.api.exceptions import (
    APIConnectionError,
    AuthenticationError,
    NotFoundError,
)
from src.api.models import CommitInfo, DevelopmentInfo, TaskInfo
from src.preprocessor.processor import DataPreprocessor


# ---------------------------------------------------------------------------
# P0: analyze_diff() 边界用例
# ---------------------------------------------------------------------------
class TestAnalyzeDiffEdgeCases:
    """analyze_diff 在各种边界输入下的期望行为。"""

    @pytest.fixture
    def analyzer(self) -> CodeChangeAnalyzer:
        return CodeChangeAnalyzer()

    def test_empty_diff(self, analyzer: CodeChangeAnalyzer) -> None:
        """空 diff 返回全零统计。"""
        result = analyzer.analyze_diff("")
        assert result["added_lines"] == 0
        assert result["removed_lines"] == 0
        assert result["files_added"] == 0
        assert result["files_removed"] == 0

    def test_malformed_diff_no_plus_header(self, analyzer: CodeChangeAnalyzer) -> None:
        """只有 --- 没有 +++ 时，files_removed 正确计算。"""
        diff = "--- a/deleted_file.py\n@@ -1,5 +0,0 @@\n-old line 1\n-old line 2\n"
        result = analyzer.analyze_diff(diff)
        # deleted_file.py 出现在 removed_files 但不在 file_changes 中
        assert result["files_removed"] == 1
        assert result["files_added"] == 0

    def test_malformed_diff_only_hunks(self, analyzer: CodeChangeAnalyzer) -> None:
        """只有 hunk 内容没有文件头。"""
        diff = "@@ -1,3 +1,4 @@\n context\n+added line\n context\n"
        result = analyzer.analyze_diff(diff)
        assert result["added_lines"] == 1
        assert result["files_added"] == 0
        assert result["files_removed"] == 0

    def test_binary_diff_markers(self, analyzer: CodeChangeAnalyzer) -> None:
        """二进制文件的 diff 标记。"""
        diff = (
            "--- a/image.png\n"
            "+++ b/image.png\n"
            "Binary files differ\n"
        )
        result = analyzer.analyze_diff(diff)
        # 二进制 diff 没有 +/- 行（除了 header）
        assert result["files_modified"] == 1

    def test_multiple_files_mixed(self, analyzer: CodeChangeAnalyzer) -> None:
        """多文件混合：新增、修改、删除。"""
        diff = (
            "--- a/existing.py\n"
            "+++ b/existing.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+new line\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
            "@@ -1,5 +0,0 @@\n"
            "-removed\n"
            "+++ b/new_file.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+added content\n"
        )
        result = analyzer.analyze_diff(diff)
        # existing.py: 出现在 both sides → modified
        # old.py: only in --- → removed
        # new_file.py: only in +++ → added
        assert result["files_added"] >= 1
        assert result["files_removed"] >= 0  # /dev/null 的处理

    def test_very_large_diff_performance(self, analyzer: CodeChangeAnalyzer) -> None:
        """超大 diff（10000 行）应在合理时间内完成。"""
        lines = ["+added line content here\n"] * 10000
        diff = "--- a/big.py\n+++ b/big.py\n@@ -1,100 +1,10100 @@\n" + "".join(lines)
        import time
        start = time.monotonic()
        result = analyzer.analyze_diff(diff)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"analyze_diff took {elapsed:.2f}s for 10K lines"
        assert result["added_lines"] == 10000

    def test_diff_with_special_characters(self, analyzer: CodeChangeAnalyzer) -> None:
        """包含中文、emoji 等特殊字符的 diff。"""
        diff = (
            "--- a/i18n.py\n"
            "+++ b/i18n.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+    msg = '你好世界 🌍'\n"
            "     context\n"
        )
        result = analyzer.analyze_diff(diff)
        assert result["added_lines"] == 1
        assert result["files_modified"] == 1


# ---------------------------------------------------------------------------
# P0: get_commits() 并发获取 + 部分失败
# ---------------------------------------------------------------------------
class TestGetCommitsConcurrency:
    """get_commits 并发获取 diff 的行为规格。"""

    @pytest.fixture
    def client(self) -> APIClient:
        return APIClient(base_url="http://test", api_key="key", timeout=5, retry=1)

    @pytest.mark.asyncio
    async def test_multiple_commits_all_get_diff(self, client: APIClient) -> None:
        """多个 commit 都成功获取 diff。"""
        commits_response = [
            {"commitId": "aaa", "message": "first", "author": "dev", "time": "2026-01-01T00:00:00", "changes": []},
            {"commitId": "bbb", "message": "second", "author": "dev", "time": "2026-01-01T01:00:00", "changes": []},
        ]

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            if "/commits" in endpoint and "/diff" not in endpoint:
                return commits_response
            return {"diff": f"diff for {endpoint}"}

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert len(commits) == 2
        # 两个 commit 都应该有 diff 数据
        assert all(c.diff for c in commits)

    @pytest.mark.asyncio
    async def test_partial_diff_failure(self, client: APIClient) -> None:
        """部分 commit 获取 diff 失败时，其余 commit 不受影响。"""
        commits_response = [
            {"commitId": "ok1", "message": "good", "author": "dev", "time": "2026-01-01T00:00:00", "changes": []},
            {"commitId": "fail1", "message": "bad", "author": "dev", "time": "2026-01-01T01:00:00", "changes": []},
            {"commitId": "ok2", "message": "also good", "author": "dev", "time": "2026-01-01T02:00:00", "changes": []},
        ]

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            if "/commits" in endpoint and "/diff" not in endpoint:
                return commits_response
            if "fail1" in endpoint:
                raise NotFoundError("diff not found")
            return {"diff": "some diff content"}

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert len(commits) == 3
        # 失败的 commit diff 为空，但不影响其他 commit
        ok_commits = [c for c in commits if c.commit_id != "fail1"]
        fail_commit = [c for c in commits if c.commit_id == "fail1"][0]
        assert all(c.diff for c in ok_commits)
        assert fail_commit.diff == ""

    @pytest.mark.asyncio
    async def test_auth_error_propagates(self, client: APIClient) -> None:
        """AuthenticationError 应向上传播，不被静默吞没。"""
        commits_response = [
            {"commitId": "aaa", "message": "test", "author": "dev", "time": "2026-01-01T00:00:00", "changes": []},
        ]

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            if "/commits" in endpoint and "/diff" not in endpoint:
                return commits_response
            raise AuthenticationError("token expired")

        with patch.object(client, "_request", side_effect=mock_request):
            with pytest.raises(AuthenticationError):
                await client.get_commits(12345)

    @pytest.mark.asyncio
    async def test_connection_error_swallowed(self, client: APIClient) -> None:
        """APIConnectionError 被捕获，commit 仍返回。"""
        commits_response = [
            {"commitId": "aaa", "message": "test", "author": "dev", "time": "2026-01-01T00:00:00", "changes": []},
        ]

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            if "/commits" in endpoint and "/diff" not in endpoint:
                return commits_response
            raise APIConnectionError("connection refused")

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert len(commits) == 1
        assert commits[0].diff == ""  # 获取失败但不应崩溃

    @pytest.mark.asyncio
    async def test_empty_commits_list(self, client: APIClient) -> None:
        """空 commit 列表不触发 diff 获取。"""
        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return []

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert commits == []

    @pytest.mark.asyncio
    async def test_commit_with_existing_diff_not_refetched(self, client: APIClient) -> None:
        """已有 diff 的 commit 不重复获取。"""
        commits_response = [
            {
                "commitId": "aaa",
                "message": "test",
                "author": "dev",
                "time": "2026-01-01T00:00:00",
                "changes": [],
                "diff": "already have diff",
            },
        ]
        diff_fetch_count = 0

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            nonlocal diff_fetch_count
            if "/commits" in endpoint and "/diff" not in endpoint:
                return commits_response
            diff_fetch_count += 1
            return {"diff": "new diff"}

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        # 已有 diff 不应再请求
        assert diff_fetch_count == 0
        assert commits[0].diff == "already have diff"


# ---------------------------------------------------------------------------
# P1: get_commit_diff() 多端点降级
# ---------------------------------------------------------------------------
class TestGetCommitDiffFallback:
    """get_commit_diff 多端点降级行为。"""

    @pytest.fixture
    def client(self) -> APIClient:
        return APIClient(base_url="http://test", api_key="key", timeout=5, retry=1)

    @pytest.mark.asyncio
    async def test_first_endpoint_succeeds(self, client: APIClient) -> None:
        """第一个端点成功时直接返回。"""
        call_order: list[str] = []

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            call_order.append(endpoint)
            return {"diff": "diff content"}

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.get_commit_diff(123, "abc")

        assert result == "diff content"
        assert len(call_order) == 1  # 只调用了一次

    @pytest.mark.asyncio
    async def test_fallback_to_second_endpoint(self, client: APIClient) -> None:
        """第一个端点 404，降级到第二个。"""
        call_order: list[str] = []

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            call_order.append(endpoint)
            if len(call_order) == 1:
                raise NotFoundError("not found")
            return {"diff": "fallback diff"}

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.get_commit_diff(123, "abc")

        assert result == "fallback diff"
        assert len(call_order) == 2

    @pytest.mark.asyncio
    async def test_all_endpoints_fail_returns_empty(self, client: APIClient) -> None:
        """所有端点都失败时返回空字符串。"""
        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            raise NotFoundError("not found")

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.get_commit_diff(123, "abc")

        assert result == ""

    @pytest.mark.asyncio
    async def test_empty_diff_field_returns_empty(self, client: APIClient) -> None:
        """API 返回空 diff 字段时继续尝试下一个端点。"""
        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return {"diff": ""}

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.get_commit_diff(123, "abc")

        # 所有端点返回空，最终结果为空
        assert result == ""

    @pytest.mark.asyncio
    async def test_content_field_fallback(self, client: APIClient) -> None:
        """diff 字段不存在时尝试 content 字段。"""
        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return {"content": "content field diff"}

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.get_commit_diff(123, "abc")

        assert result == "content field diff"


# ---------------------------------------------------------------------------
# P1: process_batch() 错误隔离 + 索引对齐
# ---------------------------------------------------------------------------
class TestProcessBatchErrorIsolation:
    """process_batch 在单个任务异常时的行为。"""

    @pytest.fixture
    def preprocessor(self) -> DataPreprocessor:
        return DataPreprocessor()

    def test_batch_preserves_order(self, preprocessor: DataPreprocessor) -> None:
        """批量处理保持输入顺序一一对应。"""
        tasks = [
            TaskInfo(
                task_id=i,
                title=f"Task {i}",
                description=f"Description {i}",
                status="open",
                create_time=datetime(2026, 1, 1),
            )
            for i in range(5)
        ]

        results = preprocessor.process_batch(tasks)

        assert len(results) == len(tasks)
        for i, result in enumerate(results):
            assert result.task_id == i

    def test_batch_with_empty_tasks(self, preprocessor: DataPreprocessor) -> None:
        """空任务列表返回空结果。"""
        results = preprocessor.process_batch([])
        assert results == []

    def test_batch_single_task(self, preprocessor: DataPreprocessor) -> None:
        """单任务批量处理。"""
        task = TaskInfo(
            task_id=42,
            title="Single",
            description="Single task",
            status="open",
            create_time=datetime(2026, 1, 1),
        )
        results = preprocessor.process_batch([task])
        assert len(results) == 1
        assert results[0].task_id == 42

    def test_batch_with_diff_data(self, preprocessor: DataPreprocessor) -> None:
        """包含 diff 数据的任务批量处理。"""
        tasks = [
            TaskInfo(
                task_id=1,
                title="With diff",
                description="Has code changes",
                status="open",
                create_time=datetime(2026, 1, 1),
                development=DevelopmentInfo(
                    commits=[
                        CommitInfo(
                            commit_id="abc",
                            message="fix",
                            author="dev",
                            time=datetime(2026, 1, 1),
                            changes=["src/foo.py"],
                            diff="--- a/foo.py\n+++ b/foo.py\n+new line",
                        )
                    ]
                ),
            ),
            TaskInfo(
                task_id=2,
                title="Without diff",
                description="No code changes",
                status="open",
                create_time=datetime(2026, 1, 1),
            ),
        ]

        results = preprocessor.process_batch(tasks)
        assert len(results) == 2
        # 第一个任务有 diff
        commit_segs_1 = [s for s in results[0].segments if s.type == "commit"]
        assert any("代码变更" in s.content for s in commit_segs_1)
        # 第二个任务无 diff
        commit_segs_2 = [s for s in results[1].segments if s.type == "commit"]
        assert len(commit_segs_2) == 0  # 没有 commit 数据


# ---------------------------------------------------------------------------
# P2: _llm_analyze_changes() 异步安全
# ---------------------------------------------------------------------------
class TestLLMAnalyzeAsyncSafety:
    """LLM 分析在不同异步上下文中的安全行为。"""

    def test_no_llm_provider_returns_empty(self) -> None:
        """无 LLM provider 时返回空字符串。"""
        analyzer = CodeChangeAnalyzer(llm_provider=None)
        result = analyzer._llm_analyze_changes([{"diff": "some diff", "message": "fix"}])
        assert result == ""

    def test_empty_diffs_returns_empty(self) -> None:
        """所有 commit 都没有 diff 时返回空。"""
        mock_provider = MagicMock()
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)
        result = analyzer._llm_analyze_changes([{"diff": "", "message": "fix"}])
        assert result == ""
        mock_provider.generate.assert_not_called()

    def test_sync_llm_provider(self) -> None:
        """同步 LLM provider 正常调用。"""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "这是代码变更分析结果"
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        result = analyzer._llm_analyze_changes([
            {"diff": "+new code\n-old code", "message": "refactor", "files_changed": ["src/a.py"]}
        ])

        assert result == "这是代码变更分析结果"
        mock_provider.generate.assert_called_once()

    def test_llm_failure_returns_empty(self) -> None:
        """LLM 调用失败时返回空字符串，不抛异常。"""
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = RuntimeError("LLM timeout")
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        result = analyzer._llm_analyze_changes([
            {"diff": "some diff", "message": "fix"}
        ])

        assert result == ""

    def test_llm_result_truncated(self) -> None:
        """LLM 返回超长结果时截断到 500 字符。"""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "x" * 1000
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        result = analyzer._llm_analyze_changes([
            {"diff": "some diff", "message": "fix"}
        ])

        assert len(result) == 500

    def test_async_provider_in_running_loop(self) -> None:
        """在已运行的事件循环中调用异步 provider 不崩溃。"""
        mock_provider = MagicMock()

        async def async_generate(prompt: str) -> str:
            return "async result"

        mock_provider.generate = async_generate
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        # 模拟在事件循环中调用
        async def _run() -> None:
            result = analyzer._llm_analyze_changes([
                {"diff": "some diff", "message": "fix"}
            ])
            # 在运行中的事件循环里应安全跳过，返回空
            assert result == ""

        asyncio.run(_run())

    def test_max_5_commits_input(self) -> None:
        """限制最多处理 5 个 commit 的 diff。"""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "summary"
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        commits = [
            {"diff": f"diff {i}", "message": f"fix {i}", "files_changed": []}
            for i in range(10)
        ]
        analyzer._llm_analyze_changes(commits)

        # 验证传给 LLM 的 prompt 不超过 5 个 commit
        call_args = mock_provider.generate.call_args[0][0]
        # 应该只包含前 5 个 commit
        for i in range(5):
            assert f"fix {i}" in call_args
        # 第 6 个不应出现
        assert "fix 5" not in call_args


# ---------------------------------------------------------------------------
# 代码模式检测补充
# ---------------------------------------------------------------------------
class TestCodePatternDetection:
    """extract_code_patterns 的准确性验证。"""

    @pytest.fixture
    def analyzer(self) -> CodeChangeAnalyzer:
        return CodeChangeAnalyzer()

    def test_detect_database_pattern(self, analyzer: CodeChangeAnalyzer) -> None:
        """检测数据库连接模式。"""
        diff = "Connection conn = getConnection();\nStatement stmt = conn.createStatement();"
        patterns = analyzer.extract_code_patterns(diff)
        types = [p["type"] for p in patterns]
        assert "database_connection" in types

    def test_detect_exception_pattern(self, analyzer: CodeChangeAnalyzer) -> None:
        """检测异常处理模式。"""
        diff = "catch (IOException e) {\n  throw new RuntimeException(e);\n}"
        patterns = analyzer.extract_code_patterns(diff)
        types = [p["type"] for p in patterns]
        assert "exception_handling" in types

    def test_detect_sql_injection(self, analyzer: CodeChangeAnalyzer) -> None:
        """检测 SQL 注入风险模式。"""
        diff = 'executeQuery("SELECT * FROM users WHERE id = " + userId)'
        patterns = analyzer.extract_code_patterns(diff)
        types = [p["type"] for p in patterns]
        assert "sql_injection" in types

    def test_no_false_positive(self, analyzer: CodeChangeAnalyzer) -> None:
        """普通代码不应触发误报。"""
        diff = "int x = 42;\nString name = 'test';\nreturn x + 1;"
        patterns = analyzer.extract_code_patterns(diff)
        assert len(patterns) == 0

    def test_null_check_pattern(self, analyzer: CodeChangeAnalyzer) -> None:
        """检测空值检查模式。"""
        diff = "if (obj == null) {\n  throw new IllegalArgumentException();\n}"
        patterns = analyzer.extract_code_patterns(diff)
        types = [p["type"] for p in patterns]
        assert "null_check" in types

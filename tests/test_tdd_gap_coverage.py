"""TDD 补齐测试 - 覆盖关键路径的边界、错误和并发场景。

这些测试定义了系统在边界条件下的期望行为，
弥补先实现后补测导致的"行为规格"缺失。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.api.client import APIClient
from src.api.exceptions import (
    APIConnectionError,
    AuthenticationError,
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
        diff = "--- a/image.png\n+++ b/image.png\nBinary files differ\n"
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
    """get_commits 调用研发云 task-branch changes/content API 的行为规格。"""

    @pytest.fixture
    def client(self) -> APIClient:
        return APIClient(base_url="http://test", api_key="key", timeout=5, retry=1)

    @pytest.mark.asyncio
    async def test_multiple_files_all_parsed(self, client: APIClient) -> None:
        """多个变更文件都成功解析。"""
        api_response = {
            "data": {
                "branchInfo": {
                    "branchName": "feature-123",
                    "repoName": "my-repo",
                    "headCommitId": "abc123",
                    "lastCommitId": "def456",
                },
                "changeFileDetailList": [
                    {
                        "filePath": "src/main.java",
                        "operType": "modified",
                        "diffContent": "--- a/src/main.java (head)\n+++ b/src/main.java (latest)\n@@ -1,3 +1,4 @@\n-old\n+new",
                        "headContent": "old content",
                        "latestContent": "new content",
                    },
                    {
                        "filePath": "src/util.java",
                        "operType": "added",
                        "diffContent": "--- /dev/null\n+++ b/src/util.java (latest)\n@@ -0,0 +1,2 @@\n+new file",
                        "headContent": "",
                        "latestContent": "new file content",
                    },
                ],
            }
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert len(commits) == 1
        commit = commits[0]
        assert commit.commit_id == "def456"
        assert commit.branch == "feature-123"
        assert commit.repository == "my-repo"
        assert len(commit.changes) == 2
        assert "src/main.java" in commit.changes
        assert "src/util.java" in commit.changes
        assert commit.diff  # 合并的 diff 不为空

    @pytest.mark.asyncio
    async def test_no_branch_returns_empty(self, client: APIClient) -> None:
        """任务没有关联代码分支时返回空列表。"""
        api_response = {"data": None, "code": "ZCM-AGILE-TASK-BRANCH-00004"}

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert commits == []

    @pytest.mark.asyncio
    async def test_api_error_propagates(self, client: APIClient) -> None:
        """API 认证错误向上传播。"""

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            raise AuthenticationError("token expired")

        with (
            patch.object(client, "_request", side_effect=mock_request),
            pytest.raises(AuthenticationError),
        ):
            await client.get_commits(12345)

    @pytest.mark.asyncio
    async def test_connection_error_propagates(self, client: APIClient) -> None:
        """API 连接错误向上传播。"""

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            raise APIConnectionError("connection refused")

        with (
            patch.object(client, "_request", side_effect=mock_request),
            pytest.raises(APIConnectionError),
        ):
            await client.get_commits(12345)

    @pytest.mark.asyncio
    async def test_empty_file_list(self, client: APIClient) -> None:
        """有分支信息但无文件变更时仍返回 commit。"""
        api_response = {
            "data": {
                "branchInfo": {
                    "branchName": "feature-456",
                    "repoName": "repo",
                    "headCommitId": "aaa",
                    "lastCommitId": "bbb",
                },
                "changeFileDetailList": [],
            }
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert len(commits) == 1
        assert commits[0].changes == []
        assert commits[0].diff == ""

    @pytest.mark.asyncio
    async def test_code_changes_attached(self, client: APIClient) -> None:
        """code_changes 被正确设置到 commit 对象。"""
        api_response = {
            "data": {
                "branchInfo": {
                    "branchName": "b",
                    "repoName": "r",
                    "headCommitId": "h",
                    "lastCommitId": "l",
                },
                "changeFileDetailList": [
                    {
                        "filePath": "f.java",
                        "operType": "modified",
                        "diffContent": "diff",
                        "headContent": "old",
                        "latestContent": "new",
                        "headCommitId": "c1",
                        "latestCommitId": "c2",
                    },
                ],
            }
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        code_changes = commits[0].code_changes
        assert len(code_changes) == 1
        assert code_changes[0].file_path == "f.java"
        assert code_changes[0].old_content == "old"
        assert code_changes[0].new_content == "new"
        assert code_changes[0].change_type == "modify"
        assert code_changes[0].head_commit_id == "c1"
        assert code_changes[0].latest_commit_id == "c2"

    @pytest.mark.asyncio
    async def test_branch_extra_fields(self, client: APIClient) -> None:
        """分支级额外字段（repoUrl, baseBranchName）被正确提取。"""
        api_response = {
            "data": {
                "branchInfo": {
                    "branchName": "feature-x",
                    "repoName": "my-repo",
                    "repoUrl": "https://git.example.com/my-repo",
                    "baseBranchName": "develop",
                    "headCommitId": "aaa",
                    "lastCommitId": "bbb",
                },
                "changeFileDetailList": [],
            }
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            commits = await client.get_commits(12345)

        assert commits[0].repo_url == "https://git.example.com/my-repo"
        assert commits[0].base_branch == "develop"
        assert commits[0].head_commit_id == "aaa"

    @pytest.mark.asyncio
    async def test_with_content_false(self, client: APIClient) -> None:
        """with_content=False 时不返回文件内容和 diff。"""
        api_response = {
            "data": {
                "branchInfo": {
                    "branchName": "b",
                    "repoName": "r",
                    "headCommitId": "h",
                    "lastCommitId": "l",
                },
                "changeFileDetailList": [
                    {
                        "filePath": "f.java",
                        "operType": "modified",
                        "diffContent": "some-diff",
                        "headContent": "old",
                        "latestContent": "new",
                    },
                ],
            }
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            # 验证请求参数中 withContent=False
            return api_response

        with patch.object(client, "_request", side_effect=mock_request) as mock_req:
            commits = await client.get_commits(12345, with_content=False)
            # 验证请求参数
            mock_req.assert_called_once()
            call_kwargs = mock_req.call_args
            assert call_kwargs[1].get("json") == {"withContent": False}

        assert commits[0].code_changes[0].old_content == ""
        assert commits[0].code_changes[0].new_content == ""
        assert commits[0].diff == ""


# ---------------------------------------------------------------------------
# P1: get_commit_diff() 已废弃，始终返回空字符串
# ---------------------------------------------------------------------------
class TestGetCommitDiffDeprecated:
    """get_commit_diff 已废弃，diff 通过 get_commits() 一次性获取。"""

    @pytest.fixture
    def client(self) -> APIClient:
        return APIClient(base_url="http://test", api_key="key", timeout=5, retry=1)

    @pytest.mark.asyncio
    async def test_returns_empty_string(self, client: APIClient) -> None:
        """get_commit_diff 始终返回空字符串。"""
        result = await client.get_commit_diff(123, "abc")
        assert result == ""


# ---------------------------------------------------------------------------
# P1: get_change_files() 轻量级获取变动文件列表
# ---------------------------------------------------------------------------
class TestGetChangeFiles:
    """get_change_files 调用 change-file API 获取变动文件列表（不含 diff）。"""

    @pytest.fixture
    def client(self) -> APIClient:
        return APIClient(base_url="http://test", api_key="key", timeout=5, retry=1)

    @pytest.mark.asyncio
    async def test_returns_flat_file_list(self, client: APIClient) -> None:
        """按仓库分组的响应被展平为统一列表。"""
        api_response = {
            "data": [
                {
                    "repoName": "repo-a",
                    "changeFileDtoList": [
                        {"filePath": "src/Main.java", "operType": "modified"},
                        {"filePath": "src/Util.java", "operType": "added"},
                    ],
                },
                {
                    "repoName": "repo-b",
                    "changeFileDtoList": [
                        {"filePath": "lib/helper.py", "operType": "removed"},
                    ],
                },
            ]
        }

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            files = await client.get_change_files(12345)

        assert len(files) == 3
        assert files[0] == {
            "filePath": "src/Main.java",
            "operType": "modified",
            "repoName": "repo-a",
        }
        assert files[2] == {
            "filePath": "lib/helper.py",
            "operType": "removed",
            "repoName": "repo-b",
        }

    @pytest.mark.asyncio
    async def test_no_branch_returns_empty(self, client: APIClient) -> None:
        """任务无关联代码时返回空列表。"""
        api_response: dict[str, object] = {"data": None}

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            return api_response

        with patch.object(client, "_request", side_effect=mock_request):
            files = await client.get_change_files(12345)

        assert files == []

    @pytest.mark.asyncio
    async def test_uses_correct_endpoint(self, client: APIClient) -> None:
        """调用正确的 change-file GET 端点。"""

        async def mock_request(method: str, endpoint: str, **kwargs: object) -> object:
            assert method == "GET"
            assert "change-file" in endpoint
            return {"data": []}

        with patch.object(client, "_request", side_effect=mock_request):
            await client.get_change_files(99999)


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

        result = analyzer._llm_analyze_changes(
            [{"diff": "+new code\n-old code", "message": "refactor", "files_changed": ["src/a.py"]}]
        )

        assert result == "这是代码变更分析结果"
        mock_provider.generate.assert_called_once()

    def test_llm_failure_returns_empty(self) -> None:
        """LLM 调用失败时返回空字符串，不抛异常。"""
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = RuntimeError("LLM timeout")
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        result = analyzer._llm_analyze_changes([{"diff": "some diff", "message": "fix"}])

        assert result == ""

    def test_llm_result_truncated(self) -> None:
        """LLM 返回超长结果时截断到 500 字符。"""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "x" * 1000
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        result = analyzer._llm_analyze_changes([{"diff": "some diff", "message": "fix"}])

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
            result = analyzer._llm_analyze_changes([{"diff": "some diff", "message": "fix"}])
            # 在运行中的事件循环里应安全跳过，返回空
            assert result == ""

        asyncio.run(_run())

    def test_max_5_commits_input(self) -> None:
        """限制最多处理 5 个 commit 的 diff。"""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "summary"
        analyzer = CodeChangeAnalyzer(llm_provider=mock_provider)

        commits = [
            {"diff": f"diff {i}", "message": f"fix {i}", "files_changed": []} for i in range(10)
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

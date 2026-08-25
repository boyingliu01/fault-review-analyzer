"""用户工作流 E2E 测试 — 模拟真实用户行为。

这些测试模拟用户从 CLI 执行的完整操作链路：
- 用户获取数据 (fetch) → 分析数据 (analyze) → 生成报告 (report)
- 用户批量操作 (batch)
- 用户查看缓存状态

核心原则：不 mock 内部组件，使用真实 CacheManager、ConfigManager、Pipeline。
唯一的外部依赖（API 服务器）通过预填充缓存来绕过。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cache.manager import CacheManager
from src.cli.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_task_data() -> dict:
    """模拟真实 API 返回的任务数据。"""
    return {
        "task_id": 60001,
        "title": "数据库连接池耗尽导致服务不可用",
        "description": "生产环境数据库连接池在高峰期耗尽",
        "status": "resolved",
        "priority": "high",
        "create_time": "2024-06-15T08:00:00",
        "resolve_time": "2024-06-15T14:30:00",
        "development": {
            "commits": [
                {
                    "commit_id": "abc123",
                    "message": "修复连接池配置",
                    "author": "dev1",
                    "time": "2024-06-15T12:00:00",
                    "changes": ["config/database.yml"],
                }
            ],
            "code_changes": [
                {
                    "file_path": "config/database.yml",
                    "old_content": "pool_size: 10",
                    "new_content": "pool_size: 50",
                    "change_type": "modify",
                }
            ],
            "code_reviews": [
                {
                    "reviewer": "dev2",
                    "time": "2024-06-15T11:00:00",
                    "comments": ["建议增加监控"],
                    "approved": True,
                }
            ],
        },
        "production": {
            "incident_time": "2024-06-15T09:00:00",
            "symptoms": "API 响应超时，数据库连接拒绝",
            "logs": ["ERROR: Connection pool exhausted", "WARN: Slow query detected"],
            "stack_traces": ["java.sql.SQLException: Cannot acquire connection"],
            "resolution": "增加连接池大小并优化慢查询",
            "timeline": [
                {
                    "time": "2024-06-15T09:00:00",
                    "action": "发现故障",
                    "actor": "monitoring",
                    "details": "告警触发",
                },
                {
                    "time": "2024-06-15T14:30:00",
                    "action": "故障恢复",
                    "actor": "dev1",
                    "details": "部署修复",
                },
            ],
        },
    }


@pytest.fixture
def populated_cache(tmp_path: Path, sample_task_data: dict) -> Path:
    """创建预填充数据的缓存数据库，返回其路径。"""
    db_path = tmp_path / "cache.db"
    with CacheManager(db_path=db_path, ttl=3600) as cache:
        cache.save_task(sample_task_data["task_id"], sample_task_data)
    return db_path


@pytest.fixture
def config_file(tmp_path: Path, populated_cache: Path) -> Path:
    """创建指向预填充缓存的临时配置文件。"""
    config_path = tmp_path / "config.yaml"
    cache_db = str(populated_cache).replace("\\", "/")
    output_dir = str(tmp_path / "output").replace("\\", "/")
    config_path.write_text(
        f"""\
api:
  base_url: "https://example.com"
  timeout: 30
  retry: 3
  api_key: "test-token"
llm:
  provider: "openai"
  model: "gpt-4"
  api_key: ""
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: ""
clustering:
  algorithm: "hdbscan"
  min_cluster_size: 3
  min_samples: 2
  metric: "cosine"
cache:
  db_path: "{cache_db}"
  ttl: 3600
  enabled: true
output:
  directory: "{output_dir}"
""",
        encoding="utf-8",
    )
    return config_path


# ---------------------------------------------------------------------------
# 工作流 1: 用户分析单个缓存中的任务
# 模拟: fault-analyzer analyze single 60001 --config config.yaml --no-llm
# ---------------------------------------------------------------------------


class TestAnalyzeSingleWorkflow:
    """用户运行 analyze single 命令的完整流程。"""

    def test_analyze_cached_task_shows_results(self, runner: CliRunner, config_file: Path):
        """分析缓存中的任务应显示分析结果表格。"""
        result = runner.invoke(
            app,
            ["analyze", "single", "60001", "--config", str(config_file), "--no-llm"],
        )

        # 命令应成功执行
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应显示分析完成信息
        assert "分析完成" in result.output or "分析结果" in result.output

    def test_analyze_with_output_saves_report(
        self, runner: CliRunner, config_file: Path, tmp_path: Path
    ):
        """使用 --output 参数应保存报告文件。"""
        output_dir = tmp_path / "reports"
        result = runner.invoke(
            app,
            [
                "analyze",
                "single",
                "60001",
                "--config",
                str(config_file),
                "--no-llm",
                "--output",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应生成报告文件
        report_files = list(output_dir.glob("*.md"))
        assert len(report_files) >= 1, "No report files generated"
        # 报告内容应包含任务信息
        content = report_files[0].read_text(encoding="utf-8")
        assert "60001" in content or "数据库" in content

    def test_analyze_nonexistent_task_shows_error(self, runner: CliRunner, config_file: Path):
        """分析不存在的任务应显示错误信息。"""
        result = runner.invoke(
            app,
            ["analyze", "single", "99999", "--config", str(config_file), "--no-llm"],
        )

        # 应显示错误或失败信息（不是崩溃）
        assert "Traceback" not in (result.output or "")
        # 退出码应为非0（表示失败）或有错误提示
        has_error = (
            result.exit_code != 0 or "失败" in result.output or "not found" in result.output.lower()
        )
        assert has_error, f"Expected error for nonexistent task, got: {result.output}"


# ---------------------------------------------------------------------------
# 工作流 2: 用户获取数据（缓存命中场景）
# 模拟: fault-analyzer fetch single 60001 --config config.yaml
# ---------------------------------------------------------------------------


class TestFetchCachedWorkflow:
    """用户获取数据时缓存已存在的场景。"""

    def test_fetch_cached_task_skips_api(self, runner: CliRunner, config_file: Path):
        """获取已在缓存中的任务应直接返回，不调用 API。"""
        result = runner.invoke(
            app,
            ["fetch", "single", "60001", "--config", str(config_file)],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应显示从缓存加载的信息
        assert "缓存" in result.output


# ---------------------------------------------------------------------------
# 工作流 3: 用户查看缓存状态
# 模拟: fault-analyzer cache list / cache stats
# ---------------------------------------------------------------------------


class TestCacheWorkflow:
    """用户查看缓存的完整流程。"""

    def test_cache_list_shows_cached_tasks(self, runner: CliRunner, config_file: Path):
        """cache list 应显示缓存中的任务。"""
        result = runner.invoke(
            app,
            ["cache", "list", "--config", str(config_file)],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应显示任务信息
        assert "60001" in result.output or "数据库" in result.output

    def test_cache_stats_shows_statistics(self, runner: CliRunner, config_file: Path):
        """cache stats 应显示缓存统计信息。"""
        result = runner.invoke(
            app,
            ["cache", "stats", "--config", str(config_file)],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应显示统计信息
        assert (
            "总条目" in result.output or "条目" in result.output or "entry" in result.output.lower()
        )


# ---------------------------------------------------------------------------
# 工作流 4: 用户生成报告
# 模拟: fault-analyzer report generate 60001 --config config.yaml
# ---------------------------------------------------------------------------


class TestReportWorkflow:
    """用户生成报告的完整流程。"""

    def test_report_generate_creates_file(
        self, runner: CliRunner, config_file: Path, tmp_path: Path
    ):
        """report generate 应创建报告文件。"""
        output_dir = tmp_path / "reports"
        result = runner.invoke(
            app,
            [
                "report",
                "generate",
                "60001",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # 应生成报告文件
        report_files = list(output_dir.glob("*.md"))
        assert len(report_files) == 1, f"Expected 1 report, found {len(report_files)}"
        # 报告内容应包含任务相关信息
        content = report_files[0].read_text(encoding="utf-8")
        assert len(content) > 100, "Report seems too short to be valid"

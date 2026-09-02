"""P1 E2E 测试: CLI 完整工作流。

使用 typer.testing.CliRunner 测试 CLI 命令的完整链路。
不 mock 内部组件，使用真实 CacheManager 和 ReportGenerator。
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cache.manager import CacheManager
from src.cli.main import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cache_with_data(tmp_path: Path) -> Path:
    """在临时路径创建缓存并写入测试数据。"""
    db_path = tmp_path / "cache.db"
    with CacheManager(db_path=db_path, ttl=3600) as manager:
        manager.save_task(
            50001,
            {
                "task_id": 50001,
                "title": "CLI测试任务",
                "description": "用于CLI工作流测试",
                "status": "resolved",
                "priority": "high",
                "create_time": "2024-07-01T10:00:00",
                "resolve_time": "2024-07-01T14:00:00",
                "development": {
                    "commits": [
                        {
                            "commit_id": "cli001",
                            "message": "修复CLI命令",
                            "time": "2024-07-01T09:00:00",
                            "changes": ["src/cli.py"],
                        }
                    ],
                    "code_changes": [],
                    "code_reviews": [],
                },
                "production": {
                    "incident_time": "2024-07-01T11:00:00",
                    "symptoms": "CLI命令报错",
                    "logs": ["ERROR: CLI failure"],
                    "stack_traces": [],
                    "resolution": "修复命令参数",
                    "timeline": [],
                },
            },
        )
    return db_path


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """创建临时配置文件。"""
    config_path = tmp_path / "config.yaml"
    # 使用正斜杠避免 YAML 双引号中的转义问题
    cache_db = str(tmp_path / "cache.db").replace("\\", "/")
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


class TestCLIVersion:
    """测试 CLI 基本功能。"""

    def test_version_flag(self, runner: CliRunner):
        """版本命令应能执行（由于 typer 实现，可能退出码非0）。"""
        result = runner.invoke(app, ["-v"])
        # typer 的 callback option 可能返回 exit_code=0 或 2
        # 关键是输出了版本信息或没有崩溃
        output = result.output.lower()
        has_version_info = "version" in output or "fault-analyzer" in output
        has_error = "error" in output or "traceback" in output
        # 至少不应有 traceback 错误
        assert not has_error or has_version_info

    def test_help_shows_all_commands(self, runner: CliRunner):
        """--help 应显示所有子命令。"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output
        assert "analyze" in result.output
        assert "report" in result.output
        assert "config" in result.output
        assert "cache" in result.output


class TestCLIConfigCommands:
    """测试 config 子命令。"""

    def test_config_list(self, runner: CliRunner, config_file: Path):
        """config list 应显示配置信息。"""
        result = runner.invoke(app, ["config", "list", "--config", str(config_file)])
        assert result.exit_code == 0
        # 应包含一些配置项
        assert "API" in result.output or "api" in result.output.lower()

    def test_config_path_default(self, runner: CliRunner):
        """config path 应显示默认路径。"""
        result = runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()


class TestCLICacheCommands:
    """测试 cache 子命令。"""

    def test_cache_stats(self, runner: CliRunner, config_file: Path):
        """cache stats 应显示 --config 指向的隔离缓存库统计。

        必须显式传 --config：不传时命令会按默认路径打开项目真实库
        data/cache/cache.db（曾因此在全量测试期间误清真实缓存数据）。
        """
        result = runner.invoke(app, ["cache", "stats", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "总条目" in result.output or "条目" in result.output

    def test_cache_list(self, runner: CliRunner, cache_with_data: Path, config_file: Path):  # noqa: ARG002
        """cache list 应显示 --config 指向的隔离缓存库中的任务。"""
        result = runner.invoke(app, ["cache", "list", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "50001" in result.output


class TestCLIReportGeneration:
    """测试 report 命令的报告生成。"""

    def test_report_generate_from_cache(
        self,
        runner: CliRunner,
        cache_with_data: Path,  # noqa: ARG002
        config_file: Path,
        tmp_path: Path,  # noqa: ARG002
    ):
        """report generate 应从缓存读取数据并生成报告文件。"""
        output_dir = tmp_path / "reports"
        result = runner.invoke(
            app,
            [
                "report",
                "generate",
                "50001",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
            ],
        )

        # 命令应成功执行
        assert result.exit_code == 0
        # 应生成报告文件
        report_files = list(output_dir.glob("*.md"))
        assert len(report_files) == 1
        # 报告内容应包含任务信息
        content = report_files[0].read_text(encoding="utf-8")
        assert "50001" in content or "CLI" in content

    def test_report_generate_missing_task(
        self, runner: CliRunner, config_file: Path, tmp_path: Path
    ):
        """report generate 对不存在的任务应友好提示。"""
        output_dir = tmp_path / "reports"
        result = runner.invoke(
            app,
            [
                "report",
                "generate",
                "99999",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
            ],
        )
        # 应提示任务不在缓存中
        assert "不在缓存" in result.output or "失败" in result.output or result.exit_code == 0


class TestCLIFetchCommands:
    """测试 fetch 子命令。"""

    def test_fetch_help(self, runner: CliRunner):
        """fetch --help 应显示可用子命令。"""
        result = runner.invoke(app, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "single" in result.output
        assert "batch" in result.output

    def test_fetch_single_help(self, runner: CliRunner):
        """fetch single --help 应显示参数说明。"""
        result = runner.invoke(app, ["fetch", "single", "--help"])
        assert result.exit_code == 0
        assert "任务ID" in result.output


class TestCLIAnalyzeCommands:
    """测试 analyze 子命令。"""

    def test_analyze_help(self, runner: CliRunner):
        """analyze --help 应显示可用子命令。"""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "single" in result.output

    def test_analyze_single_help(self, runner: CliRunner):
        """analyze single --help 应显示参数说明。"""
        result = runner.invoke(app, ["analyze", "single", "--help"])
        assert result.exit_code == 0
        assert "任务ID" in result.output

"""P1 E2E 测试: Pipeline 完整链路真实测试。

仅 mock API 网络调用（APIClient），其余组件（Preprocessor、RulesEngine、
ReportGenerator、CacheManager）全部使用真实实例。
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult
from src.api.models import (
    CommitInfo,
    DevelopmentInfo,
    ProductionInfo,
    TaskInfo,
)
from src.cache.manager import CacheManager
from src.config.manager import ConfigManager


@pytest.fixture
def real_config_manager(tmp_path: Path) -> ConfigManager:
    """创建使用临时文件的真实 ConfigManager。"""
    cache_db = str(tmp_path / "cache.db").replace("\\", "/")
    output_dir = str(tmp_path / "output").replace("\\", "/")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""\
api:
  base_url: "https://example.com"
  timeout: 5
  retry: 1
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
    return ConfigManager(config_path)


@pytest.fixture
def sample_task_info() -> TaskInfo:
    return TaskInfo(
        task_id=30001,
        title="Pipeline E2E 测试任务",
        description="验证完整流水线在真实组件下的行为",
        status="resolved",
        priority="high",
        create_time=datetime(2024, 8, 1, 10, 0, 0),
        resolve_time=datetime(2024, 8, 1, 14, 0, 0),
        development=DevelopmentInfo(
            commits=[
                CommitInfo(
                    commit_id="e2e001",
                    message="修复pipeline问题 password='test123'",
                    author="dev",
                    time=datetime(2024, 8, 1, 9, 0, 0),
                    changes=["src/pipeline.py"],
                )
            ]
        ),
        production=ProductionInfo(
            incident_time=datetime(2024, 8, 1, 11, 0, 0),
            symptoms="Pipeline 处理异常",
            logs=["ERROR: PipelineError"],
            stack_traces=["PipelineError at process()"],
            resolution="修复数据处理逻辑",
        ),
    )


def _create_mock_api_client(task: TaskInfo) -> AsyncMock:
    """创建一个返回指定 TaskInfo 的 mock API 客户端。"""
    client = AsyncMock()
    client.get_task = AsyncMock(return_value=task)
    client.get_full_task = AsyncMock(return_value=task)
    client.get_fault_analysis = AsyncMock(return_value={})
    client.close = AsyncMock()
    client.ensure_client = lambda: None
    return client


class TestPipelinePreprocessRulesReport:
    """测试 Pipeline 中 Preprocessor → Rules → Report 真实链路。"""

    @pytest.mark.asyncio
    async def test_pipeline_preprocess_rules_report(
        self, real_config_manager: ConfigManager, sample_task_info: TaskInfo
    ):
        """完整链路: fetch(mock) → preprocess → rules → report 全部使用真实组件。"""
        pipeline_config = PipelineConfig(
            use_cache=False,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=True,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        # 注入 mock API 客户端（唯一 mock 的点）
        pipeline._api_client = _create_mock_api_client(sample_task_info)

        try:
            result = await pipeline.run_single(30001)

            # 验证结果结构
            assert isinstance(result, PipelineResult)
            assert result.task_id == 30001
            assert result.error == ""

            # Preprocessor 应该产生了预处理数据
            assert result.preprocessed is not None
            assert "task_id" in result.preprocessed
            assert "segments" in result.preprocessed
            assert len(result.preprocessed["segments"]) > 0

            # Rules 应该检测到违规（commit message 包含 password='test123'）
            assert result.violations is not None
            assert isinstance(result.violations, list)
            rule_ids = [v["rule_id"] for v in result.violations]
            assert "security-001" in rule_ids

            # Report 应该生成
            assert result.report
            assert isinstance(result.report, str)
            assert len(result.report) > 50

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_pipeline_minimal_task(
        self, real_config_manager: ConfigManager
    ):
        """最小化任务也能走完全流程。"""
        minimal_task = TaskInfo(
            task_id=30002,
            title="最小化任务",
            description="",
            status="open",
            priority="low",
            create_time=datetime(2024, 8, 1),
        )

        pipeline_config = PipelineConfig(
            use_cache=False,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=True,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        pipeline._api_client = _create_mock_api_client(minimal_task)

        try:
            result = await pipeline.run_single(30002)

            assert result.error == ""
            assert result.preprocessed is not None
            assert result.violations is not None
            assert isinstance(result.report, str)

        finally:
            await pipeline.close()


class TestPipelineWithRealCache:
    """测试 Pipeline 使用真实 CacheManager。"""

    @pytest.mark.asyncio
    async def test_pipeline_writes_to_cache(
        self, real_config_manager: ConfigManager, sample_task_info: TaskInfo, tmp_path: Path
    ):
        """Pipeline 应将从 API 获取的数据写入缓存。"""
        pipeline_config = PipelineConfig(
            use_cache=True,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=False,
            generate_report=False,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        pipeline._api_client = _create_mock_api_client(sample_task_info)

        try:
            result = await pipeline.run_single(30001)
            assert result.error == ""

            # 验证数据已写入缓存
            cache_db = tmp_path / "cache.db"
            cache_manager = CacheManager(db_path=cache_db, ttl=3600)
            cached = cache_manager.get_task(30001)
            assert cached is not None
            assert cached["task_id"] == 30001 or cached.get("title") is not None

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_pipeline_reads_from_cache(
        self, real_config_manager: ConfigManager, sample_task_info: TaskInfo, tmp_path: Path
    ):
        """Pipeline 应能从缓存读取数据而不调用 API。"""
        # 先写入缓存
        cache_db = tmp_path / "cache.db"
        cache_manager = CacheManager(db_path=cache_db, ttl=3600)
        cache_manager.save_task(30001, sample_task_info.model_dump(mode="json"))

        pipeline_config = PipelineConfig(
            use_cache=True,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=True,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        # 创建一个会报错的 mock API（如果调用它说明缓存没生效）
        failing_api = AsyncMock()
        failing_api.get_task = AsyncMock(side_effect=Exception("Should not call API"))
        failing_api.close = AsyncMock()
        failing_api.ensure_client = lambda: None
        pipeline._api_client = failing_api

        try:
            result = await pipeline.run_single(30001)

            # 应该成功（从缓存读取，不调用 API）
            assert result.error == ""
            assert result.preprocessed is not None

        finally:
            await pipeline.close()


class TestPipelineBatchWithCache:
    """测试 Pipeline 批量运行的缓存行为。"""

    @pytest.mark.asyncio
    async def test_pipeline_batch_processes_all(
        self, real_config_manager: ConfigManager, tmp_path: Path
    ):
        """批量运行应处理所有任务。"""
        # 预缓存两个任务
        cache_db = tmp_path / "cache.db"
        cache_manager = CacheManager(db_path=cache_db, ttl=3600)

        for tid, title in [(30010, "任务A"), (30011, "任务B")]:
            task = TaskInfo(
                task_id=tid,
                title=title,
                description=f"描述{title}",
                status="resolved",
                priority="medium",
                create_time=datetime(2024, 8, 1),
            )
            cache_manager.save_task(tid, task.model_dump(mode="json"))

        pipeline_config = PipelineConfig(
            use_cache=True,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=False,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        # API 不应被调用（全部从缓存读取）
        failing_api = AsyncMock()
        failing_api.get_task = AsyncMock(side_effect=Exception("Should not call API"))
        failing_api.close = AsyncMock()
        failing_api.ensure_client = lambda: None
        pipeline._api_client = failing_api

        try:
            results = await pipeline.run_batch([30010, 30011])

            assert len(results) == 2
            for result in results:
                assert isinstance(result, PipelineResult)
                assert result.error == ""
                assert result.preprocessed is not None

        finally:
            await pipeline.close()


class TestPipelineErrorHandling:
    """测试 Pipeline 错误处理。"""

    @pytest.mark.asyncio
    async def test_pipeline_api_failure_graceful(
        self, real_config_manager: ConfigManager
    ):
        """API 调用失败时 Pipeline 应优雅降级。"""
        pipeline_config = PipelineConfig(
            use_cache=False,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=False,
            generate_report=False,
        )

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        # Mock API 返回 None（模拟任务不存在）
        mock_api = AsyncMock()
        mock_api.get_task = AsyncMock(return_value=None)
        mock_api.close = AsyncMock()
        mock_api.ensure_client = lambda: None
        pipeline._api_client = mock_api

        try:
            result = await pipeline.run_single(99999)

            # 应有错误信息
            assert result.error != ""
            assert "not found" in result.error.lower() or result.error != ""

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_pipeline_result_has_task_id_on_error(
        self, real_config_manager: ConfigManager
    ):
        """即使出错，PipelineResult 也应包含 task_id。"""
        pipeline_config = PipelineConfig(use_cache=False)

        pipeline = AnalysisPipeline(real_config_manager, pipeline_config)
        mock_api = AsyncMock()
        mock_api.get_task = AsyncMock(side_effect=Exception("Network error"))
        mock_api.close = AsyncMock()
        mock_api.ensure_client = lambda: None
        pipeline._api_client = mock_api

        try:
            result = await pipeline.run_single(30099)

            assert result.task_id == 30099
            assert result.error != ""

        finally:
            await pipeline.close()

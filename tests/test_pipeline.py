from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult


class TestPipelineConfig:
    def test_default_config(self):
        config = PipelineConfig()

        assert config.use_llm is False
        assert config.generate_labels is True
        assert config.analyze_root_cause is True
        assert config.check_rules is True
        assert config.generate_report is True

    def test_custom_config(self):
        config = PipelineConfig(
            use_llm=True,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=False,
            generate_report=False,
        )

        assert config.use_llm is True
        assert config.generate_labels is False

    def test_output_path_default(self):
        config = PipelineConfig()
        assert config.output_path == Path("./output")

    def test_output_path_custom(self):
        config = PipelineConfig(output_path=Path("./custom_output"))
        assert config.output_path == Path("./custom_output")


class TestPipelineResult:
    def test_default_result(self):
        result = PipelineResult(task_id=12345)

        assert result.task_id == 12345
        assert result.task_data is None
        assert result.preprocessed is None
        assert result.labels is None
        assert result.root_causes is None
        assert result.violations is None
        assert result.report == ""
        assert result.error == ""

    def test_result_with_data(self):
        result = PipelineResult(
            task_id=12345,
            task_data={"title": "Test"},
            preprocessed={"combined_text": "Test text"},
            labels=[{"name": "bug"}],
            root_causes=[{"cause_type": "code"}],
            violations=[],
            report="# Report",
        )

        assert result.task_id == 12345
        task_data = result.task_data
        labels = result.labels
        assert task_data is not None
        assert labels is not None
        assert task_data["title"] == "Test"
        assert len(labels) == 1
        assert result.report == "# Report"

    def test_result_with_error(self):
        result = PipelineResult(
            task_id=12345,
            error="Something went wrong",
        )

        assert result.error == "Something went wrong"


class TestAnalysisPipeline:
    @pytest.fixture
    def mock_config(self, temp_dir):
        config = MagicMock()
        config.api = MagicMock()
        config.api.base_url = "https://api.example.com"
        config.api.token = "test-token"
        config.llm = MagicMock()
        config.llm.api_key = ""
        config.llm.model = "gpt-4"
        config.llm.base_url = ""
        config.llm.temperature = 0.7
        config.llm.max_tokens = 4096
        config.embedding = MagicMock()
        config.embedding.provider = "openai"
        config.embedding.model = "text-embedding-3-small"
        config.embedding.api_key = ""
        config.cache = MagicMock()
        config.cache.enabled = True
        config.cache.storage = str(temp_dir / "cache.db")
        return config

    @pytest.fixture
    def pipeline_config(self):
        return PipelineConfig(
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=True,
        )

    def test_pipeline_init(self, mock_config, pipeline_config):
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        assert pipeline._pipeline_config.use_llm is False

    @pytest.mark.asyncio
    async def test_pipeline_context_manager(self, mock_config, pipeline_config):
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        async with pipeline as p:
            assert p is pipeline

    @pytest.mark.asyncio
    async def test_run_single_without_llm(self, mock_config, pipeline_config):
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task

            async with pipeline:
                result = await pipeline.run_single(12345)

            assert result.task_id == 12345
            assert result.task_data is not None
            assert result.preprocessed is not None

    @pytest.mark.asyncio
    async def test_run_single_task_not_found(self, mock_config, pipeline_config):
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            async with pipeline:
                result = await pipeline.run_single(99999)

            assert result.task_id == 99999
            assert result.error is not None
            assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_run_batch(self, mock_config, pipeline_config):
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task

            async with pipeline:
                results = await pipeline.run_batch([12345, 12346])

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_run_clustering(self, mock_config, pipeline_config):
        """测试聚类分析"""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_tasks = [
            TaskInfo(
                task_id=12345,
                title="Task 1",
                description="Description 1",
                status="open",
                priority="medium",
                create_time=datetime.now(),
            ),
            TaskInfo(
                task_id=12346,
                title="Task 2",
                description="Description 2",
                status="open",
                priority="medium",
                create_time=datetime.now(),
            ),
        ]

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )

            with patch.object(pipeline, "_get_embedding_generator") as mock_emb:
                mock_emb_gen = MagicMock()
                mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
                mock_emb.return_value = mock_emb_gen

                with patch.object(pipeline, "_get_cluster_analyzer") as mock_clust:
                    mock_cluster = MagicMock()
                    from src.clustering.models import ClusterResult

                    mock_result = MagicMock(spec=ClusterResult)
                    mock_result.labels = [0, 0]
                    mock_result.n_clusters = 1
                    mock_result.n_noise = 0
                    mock_cluster.fit_predict.return_value = mock_result
                    mock_clust.return_value = mock_cluster

                    async with pipeline:
                        result = await pipeline.run_clustering([12345, 12346])

        assert "tasks" in result
        assert result["total_requested"] == 2
        assert result["total_found"] == 2

    @pytest.mark.asyncio
    async def test_run_clustering_no_tasks(self, mock_config, pipeline_config):
        """测试聚类分析无任务情况"""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            async with pipeline:
                result = await pipeline.run_clustering([12345])

            assert "error" in result
            assert "missing_tasks" in result

    def test_check_rules(self, mock_config, pipeline_config):
        """测试规则检查"""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        task_data = {
            "title": "Test",
            "description": "Test desc",
            "development": {"commits": [{"message": "password='secret'"}]},
        }

        violations = pipeline._check_rules(task_data)

        assert isinstance(violations, list)

    def test_generate_report(self, mock_config, pipeline_config):
        """测试报告生成"""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        task_data = {
            "task_id": 12345,
            "title": "Test Task",
            "description": "Test Description",
        }
        preprocessed = {
            "segments": [
                {"type": "开发", "content": "开发内容", "metadata": {}},
            ]
        }
        labels = [
            {"name": "bug", "confidence": 0.9, "category": "issue", "description": "Bug issue"}
        ]
        root_causes = [
            {"cause_type": "代码错误", "description": "描述", "evidence": "", "confidence": 0.8}
        ]

        report = pipeline._generate_report(task_data, preprocessed, labels, root_causes)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_convert_api_to_existing_analysis(self, mock_config, pipeline_config):
        """测试 API 数据转换"""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        api_data = {
            "apiDevTaskAnalysis": {
                "catalog": "开发",
                "catalogDetail": "细节",
                "reason": "原因",
                "conclusion": "结论",
                "improveStage": "阶段",
            },
            "apiTestTaskAnalysis": {
                "catalog": "测试",
                "reason": "测试原因",
            },
        }

        result = pipeline._convert_api_to_existing_analysis(api_data)

        assert result.dev_catalog == "开发"
        assert result.dev_reason == "原因"
        assert result.test_catalog == "测试"

    @pytest.mark.asyncio
    async def test_pipeline_close(self, mock_config, pipeline_config):
        """测试 pipeline 关闭"""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        # 创建一个 mock API client
        mock_api_client = MagicMock()
        mock_api_client.close = AsyncMock()
        pipeline._api_client = mock_api_client

        await pipeline.close()

        mock_api_client.close.assert_called_once()
        assert pipeline._api_client is None

    @pytest.mark.asyncio
    async def test_pipeline_close_closes_and_clears_cache(self, mock_config, pipeline_config):
        pipeline = AnalysisPipeline(config=mock_config, pipeline_config=pipeline_config)
        mock_cache_manager = MagicMock()
        pipeline._cache_manager = mock_cache_manager

        await pipeline.close()

        mock_cache_manager.close.assert_called_once()
        assert pipeline._cache_manager is None

    @pytest.mark.asyncio
    async def test_run_single_preprocess_raises_exception(self, mock_config, pipeline_config):
        """Preprocess raises exception → caught, result.error set."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task

            # Make preprocessor.process raise an exception
            with patch.object(
                pipeline._preprocessor, "process", side_effect=ValueError("Bad data")
            ):
                async with pipeline:
                    result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert result.error == "Bad data"

    @pytest.mark.asyncio
    async def test_run_single_llm_not_available(self, mock_config):
        """use_llm=True but no LLM provider → labels/root_causes empty, no crash."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline_config = PipelineConfig(
            use_llm=True,
            generate_labels=True,
            analyze_root_cause=True,
            check_rules=False,
            generate_report=False,
        )

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch(
                "src.analyzer.pipeline.create_llm_provider", return_value=None
            ) as mock_llm_factory,
        ):
            mock_fetch.return_value = mock_task

            async with pipeline:
                result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert result.error == ""
        assert result.labels == []
        assert result.root_causes == []
        mock_llm_factory.assert_called()

    @pytest.mark.asyncio
    async def test_run_single_all_flags_false(self, mock_config):
        """All PipelineConfig flags False → only fetch + preprocess, no analysis."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline_config = PipelineConfig(
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=False,
            generate_report=False,
        )

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task

            async with pipeline:
                result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert result.task_data is not None
        assert result.preprocessed is not None
        assert result.labels is None
        assert result.root_causes is None
        assert result.violations is None
        assert result.report == ""

    @pytest.mark.asyncio
    async def test_run_batch_empty_task_ids(self, mock_config, pipeline_config):
        """Empty task_ids list → empty results list, no crash."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        async with pipeline:
            results = await pipeline.run_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_run_batch_partial_failure(self, mock_config, pipeline_config):
        """One task fails (not found), others succeed → partial results returned."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Valid Task",
            description="Valid Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        async def mock_fetch(task_id: int):
            if task_id == 99999:
                return None
            return mock_task

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch_fn:
            mock_fetch_fn.side_effect = mock_fetch

            async with pipeline:
                results = await pipeline.run_batch([12345, 99999, 12346])

        assert len(results) == 3
        # First task succeeded
        assert results[0].task_id == 12345
        assert results[0].error == ""
        assert results[0].task_data is not None
        # Second task failed (not found)
        assert results[1].task_id == 99999
        assert "not found" in results[1].error
        # Third task succeeded
        assert results[2].task_id == 12346
        assert results[2].error == ""

    @pytest.mark.asyncio
    async def test_run_clustering_single_task(self, mock_config, pipeline_config):
        """Only 1 task provided → should still return result, not crash."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Single Task",
            description="Only one task",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch_fn:
            mock_fetch_fn.return_value = mock_task

            with patch.object(pipeline, "_get_embedding_generator") as mock_emb:
                mock_emb_gen = MagicMock()
                mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128])
                mock_emb.return_value = mock_emb_gen

                with patch.object(pipeline, "_get_cluster_analyzer") as mock_clust:
                    mock_cluster = MagicMock()
                    mock_result = MagicMock()
                    mock_result.labels = [0]
                    mock_result.n_clusters = 1
                    mock_result.n_noise = 0
                    mock_cluster.fit_predict.return_value = mock_result
                    mock_clust.return_value = mock_cluster

                    async with pipeline:
                        result = await pipeline.run_clustering([12345])

        assert "tasks" in result
        assert result["total_requested"] == 1
        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_run_clustering_all_missing(self, mock_config, pipeline_config):
        """All task IDs not found → error result with missing_tasks."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch_fn:
            mock_fetch_fn.return_value = None

            async with pipeline:
                result = await pipeline.run_clustering([99999, 88888])

        assert "error" in result
        assert "No tasks to cluster" in result["error"]
        assert result["missing_tasks"] == [99999, 88888]

    def test_generate_report_with_none_data(self, mock_config, pipeline_config):
        """Report generation with None labels and None root_causes → should not crash."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        task_data = {"task_id": 12345, "title": "Test", "description": ""}
        preprocessed: dict[str, Any] = {"segments": []}

        report = pipeline._generate_report(task_data, preprocessed, None, None)

        assert isinstance(report, str)
        assert len(report) > 0

    @pytest.mark.asyncio
    async def test_close_idempotent(self, mock_config, pipeline_config):
        """Calling close() multiple times should be safe (idempotent)."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_api_client = MagicMock()
        mock_api_client.close = AsyncMock()
        pipeline._api_client = mock_api_client

        await pipeline.close()
        assert pipeline._api_client is None

        # Second close should not raise
        await pipeline.close()
        assert pipeline._api_client is None

    @pytest.mark.asyncio
    async def test_context_manager_exit_calls_close(self, mock_config, pipeline_config):
        """__aexit__ should invoke close(), cleaning up API client."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_api_client = MagicMock()
        mock_api_client.close = AsyncMock()
        pipeline._api_client = mock_api_client

        async with pipeline:
            pass  # Just enter and exit

        mock_api_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_single_exception_mid_pipeline(self, mock_config, pipeline_config):
        """Exception during check_rules → caught, error set on result."""
        from datetime import datetime

        from src.api.models import TaskInfo

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=pipeline_config,
        )

        mock_task = TaskInfo(
            task_id=12345,
            title="Test Task",
            description="Test Description",
            status="open",
            priority="medium",
            create_time=datetime.now(),
        )

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task

            # Simulate rules engine crashing at runtime
            with patch.object(
                pipeline._rules_engine,
                "check",
                side_effect=RuntimeError("Rules engine unavailable"),
            ):
                async with pipeline:
                    result = await pipeline.run_single(12345)

        assert result.task_id == 12345
        assert "Rules engine unavailable" in result.error

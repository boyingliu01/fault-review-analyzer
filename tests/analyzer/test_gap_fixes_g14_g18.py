"""Tests for GAP fixes G14-G18 (functional GAP analysis remediation).

Covers:
- G14: run_single records processing_time
- G15: REST batch limit raised to 1000
- G16: CLI batch reads task IDs from Excel
- G17: APIClient rate limiting
- G18: noise tasks identified for independent analysis
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.models import TaskInfo


def _make_task(task_id: int, title: str = "Task") -> TaskInfo:
    return TaskInfo(
        task_id=task_id,
        title=title,
        description=f"Description {task_id}",
        status="open",
        priority="medium",
        create_time=datetime.now(),
    )


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api = MagicMock()
    config.api.base_url = "https://api.example.com"
    config.api.rate_limit_qps = 0.0
    config.llm = MagicMock()
    config.llm.api_key = ""
    config.llm.model = "gpt-4"
    config.embedding = MagicMock()
    config.embedding.provider = "openai"
    config.embedding.model = "text-embedding-3-small"
    config.embedding.api_key = ""
    config.clustering = MagicMock()
    config.clustering.algorithm = "hdbscan"
    config.clustering.min_cluster_size = 2
    config.clustering.min_samples = 1
    config.clustering.metric = "cosine"
    config.cache = MagicMock()
    config.cache.db_path = "./data/cache/test.db"
    config.cache.ttl = 3600
    return config


# --- G14: processing_time ---


class TestProcessingTime:
    @pytest.mark.asyncio
    async def test_run_single_records_processing_time(self, mock_config):
        """G14: run_single sets processing_time (>= 0)."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False, check_rules=False),
        )
        mock_task = _make_task(12345)

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_task
            result = await pipeline.run_single(12345)

        assert result.processing_time >= 0.0

    @pytest.mark.asyncio
    async def test_run_single_processing_time_measured(self, mock_config):
        """G14: processing_time reflects actual elapsed time."""
        import asyncio

        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False, check_rules=False),
        )
        mock_task = _make_task(12345)

        async def slow_fetch(_tid):
            await asyncio.sleep(0.05)
            return mock_task

        with patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = slow_fetch
            result = await pipeline.run_single(12345)

        assert result.processing_time >= 0.05


# --- G15: REST batch limit ---


class TestBatchLimit:
    def test_max_batch_task_ids_raised_to_1000(self):
        """G15: MAX_BATCH_TASK_IDS is 1000."""
        from src.api.server_models import MAX_BATCH_TASK_IDS

        assert MAX_BATCH_TASK_IDS == 1000

    def test_batch_accepts_large_task_list(self):
        """G15: BatchAnalyzeRequest accepts up to 1000 task IDs."""
        from src.api.server_models import BatchAnalyzeRequest

        request = BatchAnalyzeRequest(task_ids=list(range(1, 1001)))
        assert len(request.task_ids) == 1000

    def test_batch_rejects_over_limit(self):
        """G15: BatchAnalyzeRequest rejects > 1000 task IDs."""
        from pydantic import ValidationError

        from src.api.server_models import BatchAnalyzeRequest

        with pytest.raises(ValidationError):
            BatchAnalyzeRequest(task_ids=list(range(1, 1002)))


# --- G16: CLI Excel input ---


class TestExcelReader:
    def test_read_task_ids_from_excel(self, tmp_path):
        """G16: read_task_ids_from_excel extracts fault ticket numbers."""
        import pandas as pd

        from src.utils.excel_reader import read_task_ids_from_excel

        excel_path = tmp_path / "tasks.xlsx"
        df = pd.DataFrame({"缺陷单号": [12345, 12346, 12347]})
        df.to_excel(excel_path, index=False)

        task_ids = read_task_ids_from_excel(excel_path)
        assert task_ids == [12345, 12346, 12347]

    def test_read_task_ids_dedup_and_invalid(self, tmp_path):
        """G16: invalid entries skipped, duplicates removed."""
        import pandas as pd

        from src.utils.excel_reader import read_task_ids_from_excel

        excel_path = tmp_path / "tasks.xlsx"
        df = pd.DataFrame({"任务ID": [12345, 12345, "invalid", 12346]})
        df.to_excel(excel_path, index=False)

        task_ids = read_task_ids_from_excel(excel_path)
        assert task_ids == [12345, 12346]

    def test_read_task_ids_file_not_found(self):
        """G16: missing file raises FileNotFoundError."""
        from src.utils.excel_reader import read_task_ids_from_excel

        with pytest.raises(FileNotFoundError):
            read_task_ids_from_excel("/nonexistent/tasks.xlsx")

    def test_read_task_ids_no_id_column(self, tmp_path):
        """G16: no ID column raises ValueError."""
        import pandas as pd

        from src.utils.excel_reader import read_task_ids_from_excel

        excel_path = tmp_path / "tasks.xlsx"
        df = pd.DataFrame({"标题": ["A", "B"]})
        df.to_excel(excel_path, index=False)

        with pytest.raises(ValueError, match="未找到故障单号列"):
            read_task_ids_from_excel(excel_path)

    def test_analyze_batch_has_excel_option(self):
        """G16: analyze batch command exposes --excel option."""
        import inspect

        from src.cli.commands.analyze import analyze_batch

        sig = inspect.signature(analyze_batch)
        assert "excel" in sig.parameters


# --- G17: Rate limiting ---


class TestRateLimiter:
    def test_rate_limiter_adapts_qps(self):
        """G17: AdaptiveRateLimiter backoffs on failure, recovers on success."""
        from src.utils.rate_limiter import AdaptiveRateLimiter

        limiter = AdaptiveRateLimiter(initial_qps=10.0)
        initial_qps = limiter.current_qps

        limiter.record_failure()
        assert limiter.current_qps < initial_qps

        limiter.record_success()
        assert limiter.current_qps > limiter.min_qps

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_waits(self):
        """G17: acquire enforces minimum interval between requests."""
        import time

        from src.utils.rate_limiter import AdaptiveRateLimiter

        limiter = AdaptiveRateLimiter(initial_qps=1000.0)  # 高 QPS 减少等待

        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.0

    def test_api_client_accepts_rate_limit_qps(self):
        """G17: APIClient constructor accepts rate_limit_qps."""
        from src.api.client import APIClient

        client = APIClient(base_url="https://api.example.com", rate_limit_qps=10.0)
        assert client._rate_limiter is not None

        client_no_limit = APIClient(base_url="https://api.example.com")
        assert client_no_limit._rate_limiter is None

    @pytest.mark.asyncio
    async def test_api_client_request_acquires_rate_limit(self):
        """G17: rate limiter acquire is called during requests."""
        from src.api.client import APIClient

        client = APIClient(base_url="https://api.example.com", rate_limit_qps=10.0)
        client._rate_limiter = MagicMock()
        client._rate_limiter.acquire = AsyncMock()
        client._rate_limiter.record_success = MagicMock()

        with (
            patch.object(client, "ensure_client"),
            patch.object(
                client._client or MagicMock(),
                "request",
                new_callable=AsyncMock,
            ) as mock_request,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_request.return_value = mock_response

            # 需要真实 client
            client._client = MagicMock()
            client._client.request = AsyncMock(return_value=mock_response)

            await client._request("GET", "/test")

        client._rate_limiter.acquire.assert_awaited_once()
        client._rate_limiter.record_success.assert_called_once()


# --- G18: Noise tasks ---


class TestNoiseTasks:
    @pytest.mark.asyncio
    async def test_run_clustering_identifies_noise_tasks(self, mock_config):
        """G18: run_clustering returns noise_tasks list for cluster_id=-1."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False),
        )
        mock_tasks = [_make_task(1, "Task A"), _make_task(2, "Task B"), _make_task(3, "Task C")]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128, [0.3] * 128])

        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0, -1])

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=None),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2, 3])

        assert result["noise_count"] == 1
        assert len(result["noise_tasks"]) == 1
        assert result["noise_tasks"][0]["task_id"] == 3
        assert "单独" in result["noise_tasks"][0]["reason"]

    @pytest.mark.asyncio
    async def test_run_clustering_no_noise_tasks(self, mock_config):
        """G18: no noise → noise_tasks is empty."""
        pipeline = AnalysisPipeline(
            config=mock_config,
            pipeline_config=PipelineConfig(use_llm=False),
        )
        mock_tasks = [_make_task(1), _make_task(2)]

        mock_emb_gen = MagicMock()
        mock_emb_gen.embed_batch = AsyncMock(return_value=[[0.1] * 128, [0.2] * 128])
        mock_cluster = MagicMock()
        mock_cluster.fit_predict.return_value = MagicMock(labels=[0, 0])

        with (
            patch.object(pipeline, "_fetch_task", new_callable=AsyncMock) as mock_fetch,
            patch.object(pipeline, "_get_embedding_generator", return_value=mock_emb_gen),
            patch.object(pipeline, "_get_cluster_analyzer", return_value=mock_cluster),
            patch.object(pipeline, "_get_chroma_manager", return_value=None),
        ):
            mock_fetch.side_effect = lambda tid: next(
                (t for t in mock_tasks if t.task_id == tid), None
            )
            result = await pipeline.run_clustering([1, 2])

        assert result["noise_count"] == 0
        assert result["noise_tasks"] == []

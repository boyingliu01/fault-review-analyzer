import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.models import TaskInfo


@pytest.mark.asyncio
async def test_run_clustering_bounds_fetches_and_preserves_found_task_order() -> None:
    config = MagicMock()
    pipeline = AnalysisPipeline(
        config=config,
        pipeline_config=PipelineConfig(max_concurrency=2),
    )
    active_calls = 0
    max_active_calls = 0
    tasks = {
        task_id: TaskInfo(
            task_id=task_id,
            title=f"Task {task_id}",
            description=f"Description {task_id}",
            create_time=datetime(2026, 8, 23),
        )
        for task_id in (1, 3)
    }

    async def fetch_task(task_id: int) -> TaskInfo | None:
        nonlocal active_calls, max_active_calls
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        try:
            await asyncio.sleep(0)
            return tasks.get(task_id)
        finally:
            active_calls -= 1

    embedding_generator = MagicMock()
    embedding_generator.embed_batch = AsyncMock(return_value=[[0.1], [0.3]])
    cluster_analyzer = MagicMock()
    cluster_analyzer.fit_predict.return_value = MagicMock(labels=[0, 1])

    with (
        patch.object(pipeline, "_fetch_task", side_effect=fetch_task),
        patch.object(
            pipeline,
            "_get_embedding_generator",
            return_value=embedding_generator,
        ),
        patch.object(
            pipeline,
            "_get_cluster_analyzer",
            return_value=cluster_analyzer,
        ),
    ):
        result = await pipeline.run_clustering([1, 2, 3, 4])

    assert max_active_calls == 2
    assert [task["task_id"] for task in result["tasks"]] == [1, 3]
    assert result["total_found"] == 2

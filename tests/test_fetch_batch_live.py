"""Regression tests for complete payloads in the standalone live fetcher."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models import TaskInfo


@pytest.mark.asyncio
async def test_fetch_tasks_uses_full_task_payload_for_cache() -> None:
    """The live batch fetcher caches development and production data."""
    import fetch_batch_live

    task = TaskInfo(task_id=12345, title="Complete task", create_time=datetime.now())
    config = MagicMock()
    config.cache.db_path = Path("test-cache.db")
    config.cache.ttl = 3600
    config.api.base_url = "https://api.example.com"
    config.api.api_key = "test-key"
    config.api.timeout = 30
    config.api.retry = 3

    cache_manager = MagicMock()
    cache_manager.__enter__.return_value = cache_manager
    cache_manager.get_task.return_value = None

    api_client = MagicMock()
    api_client.__aenter__ = AsyncMock(return_value=api_client)
    api_client.__aexit__ = AsyncMock(return_value=None)
    api_client.get_full_task = AsyncMock(return_value=task)

    with (
        patch.object(fetch_batch_live, "TASK_IDS", [12345]),
        patch.object(fetch_batch_live, "ConfigManager") as config_manager_class,
        patch.object(fetch_batch_live, "CacheManager", return_value=cache_manager),
        patch.object(fetch_batch_live, "APIClient", return_value=api_client),
    ):
        config_manager_class.return_value.load.return_value = config
        await fetch_batch_live.fetch_tasks()

    api_client.get_full_task.assert_called_once_with(12345)
    cache_manager.save_task.assert_called_once_with(12345, task.model_dump(mode="json"))

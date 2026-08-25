import asyncio
import threading
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.handlers.fetch import FetchHandler
from src.api.models import TaskInfo


@pytest.fixture
def task_info() -> TaskInfo:
    return TaskInfo(
        task_id=12345,
        title="Cache I/O task",
        description="Task used to exercise handler cache I/O",
        status="resolved",
        priority="medium",
        create_time=datetime(2024, 1, 15, 10, 30),
    )


@pytest.mark.asyncio
async def test_fetch_task_loads_cache_off_event_loop_thread(task_info: TaskInfo) -> None:
    loop = asyncio.get_running_loop()
    loop_thread_id = threading.get_ident()
    load_started = asyncio.Event()
    release_load = threading.Event()
    load_thread_ids: list[int] = []
    cache = MagicMock()

    def load_task(task_id: int) -> dict[str, object]:
        load_thread_ids.append(threading.get_ident())
        loop.call_soon_threadsafe(load_started.set)
        assert release_load.wait(timeout=1)
        return task_info.model_dump(mode="json")

    cache.load_task.side_effect = load_task
    handler = FetchHandler(cache_manager=cache, use_cache=True)

    fetch = asyncio.create_task(handler.fetch_task(task_info.task_id))
    try:
        await asyncio.wait_for(load_started.wait(), timeout=1)
    finally:
        release_load.set()
    result = await fetch

    assert result == task_info
    assert len(load_thread_ids) == 1
    assert load_thread_ids[0] != loop_thread_id


@pytest.mark.asyncio
async def test_fetch_task_saves_cache_off_event_loop_thread(task_info: TaskInfo) -> None:
    loop = asyncio.get_running_loop()
    loop_thread_id = threading.get_ident()
    save_started = asyncio.Event()
    release_save = threading.Event()
    save_thread_ids: list[int] = []
    cache = MagicMock()
    cache.load_task.return_value = None

    def save_task(task_id: int, task_data: dict[str, object]) -> None:
        save_thread_ids.append(threading.get_ident())
        loop.call_soon_threadsafe(save_started.set)
        assert release_save.wait(timeout=1)

    cache.save_task.side_effect = save_task
    api = MagicMock()
    api.get_full_task = AsyncMock(return_value=task_info)
    handler = FetchHandler(api_client=api, cache_manager=cache, use_cache=True)

    fetch = asyncio.create_task(handler.fetch_task(task_info.task_id))
    try:
        await asyncio.wait_for(save_started.wait(), timeout=1)
    finally:
        release_save.set()
    result = await fetch

    assert result == task_info
    assert len(save_thread_ids) == 1
    assert save_thread_ids[0] != loop_thread_id
    cache.save_task.assert_called_once_with(task_info.task_id, task_info.model_dump(mode="json"))

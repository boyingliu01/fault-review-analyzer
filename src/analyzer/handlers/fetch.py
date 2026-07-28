"""FetchHandler — responsible for fetching task data from API or cache.

Issue: #13 — Pipeline 拆分重构
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.client import APIClient
    from src.cache.manager import CacheManager

from src.api.models import TaskInfo


class FetchHandler:
    """Handles fetching task data from API and cache.

    Encapsulates the data retrieval logic previously embedded in
    AnalysisPipeline, including cache lookup and API fallback.
    """

    def __init__(
        self,
        api_client: APIClient | None = None,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        self._api_client = api_client
        self._cache_manager = cache_manager
        self._use_cache = use_cache

    async def fetch_task(self, task_id: int) -> TaskInfo | None:
        """Fetch a single task from cache or API.

        Args:
            task_id: The task ID to fetch.

        Returns:
            TaskInfo if found, None otherwise.
        """
        if self._use_cache and self._cache_manager is not None:
            cached = self._cache_manager.load_task(task_id)
            if cached:
                return TaskInfo(**cached)

        if self._api_client is None:
            return None

        task = await self._api_client.get_task(task_id)

        if self._use_cache and self._cache_manager is not None:
            self._cache_manager.save_task(task_id, task.model_dump(mode="json"))

        return task

    async def fetch_tasks(self, task_ids: list[int]) -> list[TaskInfo]:
        """Fetch multiple tasks concurrently.

        Args:
            task_ids: List of task IDs to fetch.

        Returns:
            List of successfully fetched TaskInfo objects.
        """
        import asyncio

        results = await asyncio.gather(
            *[self.fetch_task(tid) for tid in task_ids],
            return_exceptions=True,
        )
        return [t for t in results if isinstance(t, TaskInfo)]

    def set_api_client(self, client: APIClient) -> None:
        """Set or replace the API client."""
        self._api_client = client

    def set_cache_manager(self, manager: CacheManager) -> None:
        """Set or replace the cache manager."""
        self._cache_manager = manager

import asyncio
from datetime import datetime
from typing import Any

import httpx

from src.api.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from src.api.models import (
    CommitInfo,
    DevelopmentInfo,
    ProductionInfo,
    TaskInfo,
)


class APIClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: int = 30,
        retry: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retry = retry
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "APIClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("APIClient must be used as async context manager")

        last_error: Exception | None = None

        for attempt in range(self.retry):
            try:
                response = await self._client.request(method, endpoint, **kwargs)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError()
                elif response.status_code == 404:
                    raise NotFoundError()
                elif response.status_code == 429:
                    raise RateLimitError()
                elif response.status_code >= 500:
                    raise ServerError(f"Server error: {response.status_code}")
                else:
                    raise APIError(
                        f"API error: {response.status_code}",
                        status_code=response.status_code,
                    )

            except httpx.ConnectError as e:
                last_error = APIConnectionError(str(e))
                if attempt < self.retry - 1:
                    await asyncio.sleep(2**attempt)
            except httpx.TimeoutException as e:
                last_error = APIConnectionError(f"Timeout: {e}")
                if attempt < self.retry - 1:
                    await asyncio.sleep(2**attempt)
            except (AuthenticationError, NotFoundError, RateLimitError):
                raise

        raise last_error or APIConnectionError("Unknown error")

    async def get_task(self, task_id: int) -> TaskInfo:
        response = await self._request("GET", f"/task/{task_id}")
        return self._parse_task(response)

    async def get_commits(self, task_id: int) -> list[CommitInfo]:
        response = await self._request("GET", f"/task/{task_id}/commits")
        return [self._parse_commit(item) for item in response]

    async def get_production_info(self, task_id: int) -> ProductionInfo:
        response = await self._request("GET", f"/task/{task_id}/production")
        return self._parse_production_info(response)

    async def get_full_task(self, task_id: int) -> TaskInfo:
        task = await self.get_task(task_id)

        try:
            commits = await self.get_commits(task_id)
            if commits:
                task.development = DevelopmentInfo(commits=commits)
        except NotFoundError:
            pass

        try:
            production = await self.get_production_info(task_id)
            task.production = production
        except NotFoundError:
            pass

        return task

    def _parse_task(self, data: dict[str, Any]) -> TaskInfo:
        return TaskInfo(
            task_id=data.get("taskId", data.get("task_id", 0)),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", ""),
            priority=data.get("priority", "medium"),
            create_time=self._parse_datetime(
                data.get("createTime", data.get("create_time", ""))
            ),
            resolve_time=self._parse_datetime(
                data.get("resolveTime", data.get("resolve_time"))
            ),
        )

    def _parse_commit(self, data: dict[str, Any]) -> CommitInfo:
        return CommitInfo(
            commit_id=data.get("commitId", data.get("commit_id", "")),
            message=data.get("message", ""),
            author=data.get("author", ""),
            time=self._parse_datetime(
                data.get("time", data.get("commitTime", ""))
            ),
            changes=data.get("changes", data.get("files", [])),
        )

    def _parse_production_info(self, data: dict[str, Any]) -> ProductionInfo:
        return ProductionInfo(
            incident_time=self._parse_datetime(
                data.get("incidentTime", data.get("incident_time", ""))
            ),
            symptoms=data.get("symptoms", ""),
            logs=data.get("logs", []),
            stack_traces=data.get("stackTraces", data.get("stack_traces", [])),
            resolution=data.get("resolution", ""),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        raise ValueError(f"Cannot parse datetime: {value}")

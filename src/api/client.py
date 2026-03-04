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
        api_key: str = "",
        timeout: int = 30,
        retry: int = 3,
        api_path_prefix: str = "/portal/ai-gateway/devspace/rpc/v3/work-item",
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or api_key
        self.timeout = timeout
        self.retry = retry
        self.api_path_prefix = api_path_prefix
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False

    async def __aenter__(self) -> "APIClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )
        self._owns_client = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    def ensure_client(self) -> None:
        """Ensure the client is initialized for non-context-manager usage."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_headers(),
            )

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            if self.token.startswith("Bearer "):
                headers["Authorization"] = self.token
            else:
                headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self._client is None:
            self.ensure_client()

        last_error: Exception | None = None

        for attempt in range(self.retry):
            try:
                assert self._client is not None
                response = await self._client.request(method, endpoint, **kwargs)

                if response.status_code == 200:
                    result = response.json()
                    return result if isinstance(result, dict) else {}
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
        response = await self._request("POST", f"{self.api_path_prefix}/{task_id}/detail", json=self._get_default_detail_body())
        return self._parse_task(response)

    def _get_default_detail_body(self) -> dict[str, Any]:
        return {
            "withTaskFlowStage": "false",
            "withOwnerUser": "false",
            "withProductModule": "false",
            "withAction": "false",
            "withParent": "false",
            "withTaskDoc": "false",
            "withDevCase": "false",
            "withTestCase": "false",
            "withTaskType": "false",
            "withProductVersion": "false",
            "withBranchVersion": "false",
            "withAttach": "false",
            "withEdo": "false",
            "withTaskImpact": "false",
            "withConfig": "false",
            "withAllTaskType": "false"
        }

    async def get_commits(self, task_id: int) -> list[CommitInfo]:
        response = await self._request("GET", f"/task/{task_id}/commits")
        commits_data: list[Any] = response if isinstance(response, list) else []
        return [self._parse_commit(item) for item in commits_data]

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
        task_data = data.get("data", {}).get("apiTask", data)
        create_time = self._parse_datetime(
            task_data.get("createdDate", task_data.get("create_time", ""))
        )
        resolve_time = self._parse_datetime(
            task_data.get("finishDate", task_data.get("resolveTime"))
        )
        from datetime import datetime as dt
        now = dt.now()
        return TaskInfo(
            task_id=task_data.get("taskId", task_data.get("task_id", 0)),
            title=task_data.get("taskTitle", task_data.get("title", "")),
            description=task_data.get("comments", task_data.get("description", "")),
            status="closed" if task_data.get("finishFlag") == 1 else "open",
            priority=self._map_priority(task_data.get("taskPriId")),
            create_time=create_time or now,
            resolve_time=resolve_time,
        )

    def _map_priority(self, pri_id: int | None) -> str:
        if pri_id is None:
            return "medium"
        priority_map = {5: "low", 10: "medium", 15: "high", 20: "critical"}
        return priority_map.get(pri_id, "medium")

    def _parse_commit(self, data: dict[str, Any]) -> CommitInfo:
        from datetime import datetime as dt

        commit_time = self._parse_datetime(
            data.get("time", data.get("commitTime", ""))
        )
        return CommitInfo(
            commit_id=data.get("commitId", data.get("commit_id", "")),
            message=data.get("message", ""),
            author=data.get("author", ""),
            time=commit_time or dt.now(),
            changes=data.get("changes", data.get("files", [])),
        )

    def _parse_production_info(self, data: dict[str, Any]) -> ProductionInfo:
        from datetime import datetime as dt

        incident_time = self._parse_datetime(
            data.get("incidentTime", data.get("incident_time", ""))
        )
        return ProductionInfo(
            incident_time=incident_time or dt.now(),
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

import asyncio
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.api.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from src.api.models import (
    CodeChange,
    CommitInfo,
    DevelopmentInfo,
    ProductionInfo,
    TaskInfo,
)
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError


class APIClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",  # nosec B107 - Default empty string for optional token
        api_key: str = "",  # nosec B107 - Default empty string for optional key
        timeout: int = 30,
        retry: int = 3,
        api_path_prefix: str = "/portal/ai-gateway/devspace/rpc/v3/work-item",
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or api_key
        self.timeout = timeout
        self.retry = retry
        self.api_path_prefix = api_path_prefix
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            name="api_client",
            failure_threshold=5,
            reset_timeout=60.0,
        )

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def __aenter__(self) -> "APIClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
            trust_env=False,  # 企业网络中避免系统代理干扰内网域名
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
                trust_env=False,  # 企业网络中避免系统代理干扰内网域名
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

        # Check circuit breaker before making request
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerError(
                self._circuit_breaker.name,
                self._circuit_breaker.reset_timeout,
            )

        last_error: Exception | None = None

        for attempt in range(self.retry):
            try:
                assert self._client is not None  # nosec B101 - Internal validation after ensure_client()
                response = await self._client.request(method, endpoint, **kwargs)

                if response.status_code == 200:
                    result = response.json()
                    self._circuit_breaker.record_success()
                    return result if isinstance(result, dict) else {}
                elif response.status_code == 401:
                    # Auth errors don't indicate service failure
                    raise AuthenticationError()
                elif response.status_code == 404:
                    # Not found errors don't indicate service failure
                    raise NotFoundError()
                elif response.status_code == 429:
                    # Rate limit - record as failure but don't retry
                    self._circuit_breaker.record_failure(RateLimitError())
                    raise RateLimitError()
                elif response.status_code >= 500:
                    # Server errors indicate service failure
                    error = ServerError(f"Server error: {response.status_code}")
                    self._circuit_breaker.record_failure(error)
                    raise error
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

        # All retries failed - record failure
        if last_error:
            self._circuit_breaker.record_failure(last_error)
        raise last_error or APIConnectionError("Unknown error")

    async def verify_token(self) -> bool:
        """Verify that the current API token is valid and can access the API.

        Makes a lightweight request to the user-info endpoint to check
        authentication. Raises clear errors for common failure modes.

        Returns:
            True if the token is valid.

        Raises:
            AuthenticationError: If token is missing, expired, or invalid.
            APIConnectionError: If the API server is unreachable.
            ServerError: If the server returns a 5xx error.
        """
        if not self.token:
            raise AuthenticationError(
                "No API token configured. Set DEVCLOUD_TOKEN environment "
                "variable or pass token to APIClient()."
            )

        if self._client is None:
            self.ensure_client()

        assert self._client is not None  # nosec B101

        try:
            response = await self._client.request(
                "POST",
                f"{self.api_path_prefix}/1/detail",
                json=self._get_default_detail_body(),
            )
        except httpx.ConnectError as e:
            raise APIConnectionError(f"Cannot reach API server: {e}") from e
        except httpx.TimeoutException as e:
            raise APIConnectionError(f"API server timeout: {e}") from e

        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            raise AuthenticationError(
                "API token is expired or invalid. "
                "Please refresh your DEVCLOUD_TOKEN and try again."
            )
        elif response.status_code >= 500:
            raise ServerError(f"Server error during token verification: {response.status_code}")
        else:
            # Any other response (404, etc.) means the server accepted our token
            return True

    async def get_task(self, task_id: int) -> TaskInfo:
        response = await self._request(
            "POST", f"{self.api_path_prefix}/{task_id}/detail", json=self._get_default_detail_body()
        )
        task = self._parse_task(response)
        if task.task_id != task_id:
            task = TaskInfo(
                task_id=task_id,
                title=task.title,
                description=task.description,
                status=task.status,
                priority=task.priority,
                create_time=task.create_time,
                resolve_time=task.resolve_time,
                requirement=task.requirement,
                design=task.design,
                development=task.development,
                testing=task.testing,
                production=task.production,
            )
        return task

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
            "withAllTaskType": "false",
        }

    async def get_commits(self, task_id: int) -> list[CommitInfo]:
        """获取任务的commit列表（含diff数据）"""
        response = await self._request("GET", f"/task/{task_id}/commits")
        commits_data: list[Any] = response if isinstance(response, list) else []
        commits = [self._parse_commit(item) for item in commits_data]

        # 尝试为每个commit获取diff数据
        for commit in commits:
            if not commit.diff and commit.commit_id:
                try:
                    diff_data = await self.get_commit_diff(task_id, commit.commit_id)
                    commit.diff = diff_data
                except Exception:
                    logger.debug(f"无法获取commit {commit.commit_id} 的diff数据")

        return commits

    async def get_commit_diff(self, task_id: int, commit_id: str) -> str:
        """获取单个commit的diff内容

        尝试多个可能的API端点来获取diff数据，支持降级。
        """
        # 尝试端点1: 标准diff端点
        endpoints = [
            f"/task/{task_id}/commit/{commit_id}/diff",
            f"/task/{task_id}/commits/{commit_id}/diff",
            f"{self.api_path_prefix}/{task_id}/commit/{commit_id}/diff",
        ]

        for endpoint in endpoints:
            try:
                response = await self._request("GET", endpoint)
                if isinstance(response, dict):
                    diff_text = response.get("diff", response.get("content", ""))
                    if diff_text:
                        return diff_text
                elif isinstance(response, str):
                    return response
            except (NotFoundError, APIConnectionError):
                continue

        return ""

    async def get_production_info(self, task_id: int) -> ProductionInfo:
        response = await self._request("GET", f"/task/{task_id}/production")
        return self._parse_production_info(response)

    async def get_full_task(self, task_id: int) -> TaskInfo:
        task = await self.get_task(task_id)

        try:
            commits = await self.get_commits(task_id)
            if commits:
                # 从commits中提取code_changes
                code_changes = [
                    CodeChange(
                        file_path=f,
                        old_content="",
                        new_content="",
                        change_type="modify",
                    )
                    for c in commits
                    for f in c.changes
                ]
                task.development = DevelopmentInfo(
                    commits=commits,
                    code_changes=code_changes,
                )
        except NotFoundError:
            pass

        try:
            production = await self.get_production_info(task_id)
            task.production = production
        except NotFoundError:
            pass

        return task

    async def get_fault_analysis(self, task_no: str) -> dict[str, Any]:
        """
        获取故障复盘结论
        接口: POST /portal/ai-gateway/devspace/rpc/v3/{taskNo}/inter-analysis
        返回: {
            "apiDevTaskAnalysis": {...},  # 研发环节分析
            "apiTestTaskAnalysis": {...},  # 测试环节分析
            "apiMgrTaskAnalysis": {...}     # 管理环节分析
        }
        """
        url = f"{self.api_path_prefix}/{task_no}/inter-analysis"
        return await self._request("POST", url, json={})

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

        commit_time = self._parse_datetime(data.get("time", data.get("commitTime", "")))
        return CommitInfo(
            commit_id=data.get("commitId", data.get("commit_id", "")),
            message=data.get("message", ""),
            author=data.get("author", ""),
            time=commit_time or dt.now(),
            changes=data.get("changes", data.get("files", [])),
            diff=data.get("diff", data.get("diffContent", data.get("patch", ""))),
            branch=data.get("branch", data.get("branchName", "")),
            repository=data.get("repository", data.get("repoName", "")),
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

        if isinstance(value, datetime):
            return value

        # 处理数值类型的时间戳
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                pass

        value_str = str(value).strip()
        if not value_str:
            return None

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value_str, fmt)
            except ValueError:
                continue

        # 尝试解析 ISO 格式（带时区）
        try:
            return datetime.fromisoformat(value_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        # 作为最后手段，不抛出异常，返回 None
        logger.warning(f"Cannot parse datetime: {value}")
        return None

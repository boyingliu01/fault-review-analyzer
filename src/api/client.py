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
from src.utils.rate_limiter import AdaptiveRateLimiter


class APIClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",  # nosec B107 - Default empty string for optional token
        api_key: str = "",  # nosec B107 - Default empty string for optional key
        timeout: int = 30,
        retry: int = 3,
        api_path_prefix: str = "/portal/ai-gateway/devspace/rpc/v3/work-item",
        code_api_prefix: str = "/portal/ai-gateway/devspace/rpc/v3",
        circuit_breaker: CircuitBreaker | None = None,
        rate_limit_qps: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or api_key
        self.timeout = timeout
        self.retry = retry
        self.api_path_prefix = api_path_prefix
        self.code_api_prefix = code_api_prefix
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            name="api_client",
            failure_threshold=5,
            reset_timeout=60.0,
        )
        # G17: 可选的自适应速率限制（rate_limit_qps=0 表示不启用）
        self._rate_limiter = (
            AdaptiveRateLimiter(initial_qps=rate_limit_qps) if rate_limit_qps > 0 else None
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

        # G17: 速率限制（可选）
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()

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
                    if self._rate_limiter is not None:
                        self._rate_limiter.record_success()
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
                    if self._rate_limiter is not None:
                        self._rate_limiter.record_failure()
                    raise RateLimitError()
                elif response.status_code >= 500:
                    # Server errors indicate service failure
                    error = ServerError(f"Server error: {response.status_code}")
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
            except ServerError as e:
                last_error = e
                if attempt < self.retry - 1:
                    await asyncio.sleep(2**attempt)
            except (AuthenticationError, NotFoundError, RateLimitError):
                raise

        # All retries failed - record the logical request once
        if last_error:
            self._circuit_breaker.record_failure(last_error)
            if self._rate_limiter is not None:
                self._rate_limiter.record_failure()
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
                "API token is expired or invalid. Please refresh your DEVCLOUD_TOKEN and try again."
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
                is_commit_code=task.is_commit_code,
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

    async def get_commits(self, task_id: int, *, with_content: bool = True) -> list[CommitInfo]:
        """获取任务的代码变更数据。

        调用研发云 POST /task-branch/{taskNo}/changes/content API，
        获取特性分支上的文件变动详情。

        Args:
            task_id: 任务单号
            with_content: 是否返回文件内容和 diff（默认 True）。
                设为 False 时仅返回文件路径和变更类型，响应更轻量。

        Returns:
            合成的 CommitInfo 列表（通常一个元素，代表整个分支的变更）。
        """
        endpoint = f"{self.code_api_prefix}/task-branch/{task_id}/changes/content"
        response = await self._request("POST", endpoint, json={"withContent": with_content})

        data = response.get("data") if isinstance(response, dict) else None
        if not data:
            return []

        branch_info = data.get("branchInfo") or {}
        file_details = data.get("changeFileDetailList") or []

        if not file_details and not branch_info.get("branchName"):
            return []

        # --- 提取分支级信息 ---
        branch_name = branch_info.get("branchName", "")
        repo_name = branch_info.get("repoName", "")
        repo_url = branch_info.get("repoUrl", "")
        base_branch = branch_info.get("baseBranchName", "")
        head_commit_id = branch_info.get("headCommitId", "")
        last_commit_id = branch_info.get("lastCommitId", "")

        # --- 提取文件级变更 ---
        all_diffs: list[str] = []
        file_paths: list[str] = []
        code_changes: list[CodeChange] = []

        for fd in file_details:
            file_path = fd.get("filePath", "") or ""
            oper_type = fd.get("operType", "modified") or "modified"
            diff_content = fd.get("diffContent") or ""
            head_content = (fd.get("headContent") or "") if with_content else ""
            latest_content = (fd.get("latestContent") or "") if with_content else ""
            fd_head_commit = fd.get("headCommitId") or ""
            fd_latest_commit = fd.get("latestCommitId") or ""

            file_paths.append(file_path)
            if with_content and diff_content:
                all_diffs.append(diff_content)

            change_type_map = {"added": "add", "modified": "modify", "removed": "delete"}
            code_changes.append(
                CodeChange(
                    file_path=file_path,
                    old_content=head_content,
                    new_content=latest_content,
                    change_type=change_type_map.get(oper_type, "modify"),
                    head_commit_id=fd_head_commit,
                    latest_commit_id=fd_latest_commit,
                )
            )

        combined_diff = "\n".join(all_diffs)
        commit_message = (
            f"[{branch_name}] {head_commit_id[:8]}..{last_commit_id[:8]}"
            if last_commit_id
            else branch_name
        )

        commit = CommitInfo(
            commit_id=last_commit_id or head_commit_id or "unknown",
            message=commit_message,
            author="",
            time=datetime.now(),
            changes=file_paths,
            diff=combined_diff,
            branch=branch_name,
            repository=repo_name,
            repo_url=repo_url,
            base_branch=base_branch,
            head_commit_id=head_commit_id,
            code_changes=code_changes,
        )

        return [commit]

    async def get_change_files(self, task_id: int) -> list[dict[str, str]]:
        """轻量级获取任务单的代码变动文件列表（不含 diff 和文件内容）。

        调用研发云 GET /task/{taskNo}/change-file API。
        传入需求单号返回其下所有任务的变动文件汇总，
        传入任务/缺陷则返回特性分支上的变动文件。

        Args:
            task_id: 任务单号

        Returns:
            变动文件列表，每项包含 filePath 和 operType。
            按仓库分组返回，已展平为统一列表。
        """
        endpoint = f"{self.code_api_prefix}/task/{task_id}/change-file"
        response = await self._request("GET", endpoint)

        data = response.get("data") if isinstance(response, dict) else None
        if not data or not isinstance(data, list):
            return []

        result: list[dict[str, str]] = []
        for repo_info in data:
            repo_name = repo_info.get("repoName", "")
            for fileDto in repo_info.get("changeFileDtoList") or []:
                result.append(
                    {
                        "filePath": fileDto.get("filePath", ""),
                        "operType": fileDto.get("operType", "modified"),
                        "repoName": repo_name,
                    }
                )
        return result

    async def get_commit_diff(self, task_id: int, commit_id: str) -> str:  # noqa: ARG002
        """获取单个commit的diff内容（已废弃，diff通过get_commits一次性获取）。

        保留此方法以兼容旧接口，实际diff数据已通过 get_commits() 获取。
        """
        return ""

    async def get_code_diffs(self, task_id: int) -> list[CommitInfo]:
        """获取任务对应 commit 的代码 diff 内容（规范命名别名）。

        与 get_commits() 等价，但提供优雅降级：API 不可用时返回空列表
        （而非抛异常），符合规范"API不可用时diff为空"的要求。

        Args:
            task_id: 任务单号

        Returns:
            含 diff 内容的 CommitInfo 列表。
        """
        try:
            return await self.get_commits(task_id, with_content=True)
        except (APIConnectionError, ServerError):
            logger.warning(f"获取代码变更失败（降级为空）: task_id={task_id}")
            return []

    async def get_production_info(self, task_id: int) -> ProductionInfo:
        response = await self._request("GET", f"/task/{task_id}/production")
        return self._parse_production_info(response)

    async def get_full_task(self, task_id: int) -> TaskInfo:
        """获取完整任务信息（含开发代码变更、生产信息、复盘结论）。"""
        task = await self.get_task(task_id)

        try:
            commits = await self.get_commits(task_id)
            if commits:
                # 直接从 commit.code_changes 汇总，无需额外 hack
                all_code_changes: list[CodeChange] = []
                for c in commits:
                    all_code_changes.extend(c.code_changes)
                task.development = DevelopmentInfo(
                    commits=commits,
                    code_changes=all_code_changes,
                )
        except (NotFoundError, APIConnectionError, ServerError):
            # 代码变更不可用时优雅降级（视为无代码变更）
            pass

        try:
            production = await self.get_production_info(task_id)
            task.production = production
        except NotFoundError:
            pass

        # G8: 将故障复盘结论纳入标准 fetch 流程（API 不可用时降级为 None）
        try:
            task.fault_analysis = await self.get_fault_analysis(str(task_id))
        except Exception:
            task.fault_analysis = None

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
        url = f"{self.code_api_prefix}/{task_no}/inter-analysis"
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
            is_commit_code=self._parse_is_commit_code(
                task_data.get("isCommitCode", task_data.get("is_commit_code"))
            ),
        )

    @staticmethod
    def _parse_is_commit_code(value: Any) -> str:
        """将 API 返回的 isCommitCode 归一化为 'Y' / 'N'。

        API 可能返回布尔、字符串 'Y'/'N'、'true'/'false' 或 1/0。
        """
        if value is None:
            return "N"
        if isinstance(value, bool):
            return "Y" if value else "N"
        if isinstance(value, (int, float)):
            return "Y" if value else "N"
        normalized = str(value).strip().lower()
        return "Y" if normalized in {"y", "yes", "true", "1"} else "N"

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

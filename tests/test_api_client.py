from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.client import APIClient
from src.api.exceptions import AuthenticationError, NotFoundError
from src.api.models import CommitInfo, ProductionInfo, TaskInfo


class TestAPIClient:
    @pytest.fixture
    def api_client(self):
        return APIClient(
            base_url="https://api.example.com",
            token="test-token",
            timeout=30,
            retry=3,
        )

    @pytest.mark.asyncio
    async def test_get_task_detail(self, api_client):
        mock_response = {
            "taskId": 12345,
            "taskTitle": "SQL查询导致OOM",
            "comments": "生产环境执行大表查询时发生内存溢出",
            "finishFlag": 1,
            "taskPriId": 15,
            "createdDate": "2024-01-15T10:00:00",
            "finishDate": "2024-01-15T12:00:00",
        }

        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            task = await api_client.get_task(12345)

            assert task.task_id == 12345
            assert task.title == "SQL查询导致OOM"
            assert task.status == "closed"

    @pytest.mark.asyncio
    async def test_authentication(self, api_client):
        headers = api_client._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, api_client):
        call_count = 0

        async def mock_http_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection error")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "taskId": 12345,
                "taskTitle": "Test",
                "comments": "Test task",
                "finishFlag": 0,
                "taskPriId": 10,
                "createdDate": "2024-01-15T10:00:00",
                "finishDate": None,
            }
            return mock_resp

        api_client.ensure_client()
        with patch("asyncio.sleep"), patch.object(
            api_client._client, "request", side_effect=mock_http_request
        ):
            result = await api_client.get_task(12345)
            assert call_count == 3
            assert result.task_id == 12345

    @pytest.mark.asyncio
    async def test_error_handling_401(self, api_client):
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = MagicMock(
                status_code=401,
                json=lambda: {"message": "Unauthorized"},
            )

            async with api_client:
                with pytest.raises(AuthenticationError):
                    await api_client._request("GET", "/task/12345")

    @pytest.mark.asyncio
    async def test_error_handling_404(self, api_client):
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.return_value = MagicMock(
                status_code=404,
                json=lambda: {"message": "Not found"},
            )

            async with api_client:
                with pytest.raises(NotFoundError):
                    await api_client._request("GET", "/task/99999")

    @pytest.mark.asyncio
    async def test_get_commits(self, api_client):
        mock_response = [
            {
                "commitId": "abc123",
                "message": "添加查询功能",
                "author": "developer",
                "time": "2024-01-15T09:00:00",
                "changes": ["src/query.py", "src/db.py"],
            }
        ]

        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            commits = await api_client.get_commits(12345)

            assert len(commits) == 1
            assert commits[0].commit_id == "abc123"

    @pytest.mark.asyncio
    async def test_get_production_info(self, api_client):
        mock_response = {
            "incidentTime": "2024-01-15T11:30:00",
            "symptoms": "内存使用率达到98%",
            "logs": ["ERROR: OutOfMemoryError"],
            "stackTraces": ["java.lang.OutOfMemoryError"],
            "resolution": "优化SQL查询",
        }

        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            info = await api_client.get_production_info(12345)

            assert info.symptoms == "内存使用率达到98%"
            assert len(info.logs) == 1

    @pytest.mark.asyncio
    async def test_context_manager(self, api_client):
        async with api_client as client:
            assert client is api_client

    @pytest.mark.asyncio
    async def test_close_client(self, api_client):
        api_client.ensure_client()
        assert api_client._client is not None
        await api_client.close()
        assert api_client._client is None

    def test_ensure_client(self, api_client):
        api_client.ensure_client()
        assert api_client._client is not None

    def test_get_headers_with_bearer_prefix(self):
        client = APIClient(
            base_url="https://api.example.com",
            token="Bearer existing-token",
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer existing-token"

    def test_get_headers_with_api_key(self):
        client = APIClient(
            base_url="https://api.example.com",
            api_key="api-key-value",
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer api-key-value"

    @pytest.mark.asyncio
    async def test_get_task_with_nested_response(self, api_client):
        mock_response = {
            "data": {
                "apiTask": {
                    "taskId": 12345,
                    "taskTitle": "SQL查询导致OOM",
                    "comments": "生产环境执行大表查询时发生内存溢出",
                    "finishFlag": 1,
                    "taskPriId": 15,
                    "createdDate": "2024-01-15T10:00:00",
                    "finishDate": "2024-01-15T12:00:00",
                }
            }
        }

        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            task = await api_client.get_task(12345)

            assert task.task_id == 12345
            assert task.title == "SQL查询导致OOM"

    @pytest.mark.asyncio
    async def test_get_task_with_alternative_fields(self, api_client):
        mock_response = {
            "task_id": 12345,
            "title": "SQL查询导致OOM",
            "description": "生产环境执行大表查询时发生内存溢出",
            "finishFlag": 0,
            "taskPriId": 10,
            "create_time": "2024-01-15T10:00:00",
        }

        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            task = await api_client.get_task(12345)

            assert task.task_id == 12345
            assert task.title == "SQL查询导致OOM"
            assert task.status == "open"


class TestAPIDataModels:
    def test_task_info_model(self):
        task = TaskInfo(
            task_id=12345,
            title="SQL查询导致OOM",
            description="生产环境执行大表查询时发生内存溢出",
            status="resolved",
            priority="high",
            create_time=datetime(2024, 1, 15, 10, 0, 0),
        )

        assert task.task_id == 12345
        assert task.title == "SQL查询导致OOM"
        assert task.status == "resolved"

    def test_commit_info_model(self):
        commit = CommitInfo(
            commit_id="abc123",
            message="添加查询功能",
            author="developer",
            time=datetime(2024, 1, 15, 9, 0, 0),
            changes=["src/query.py", "src/db.py"],
        )

        assert commit.commit_id == "abc123"
        assert len(commit.changes) == 2

    def test_production_info_model(self):
        info = ProductionInfo(
            incident_time=datetime(2024, 1, 15, 11, 30, 0),
            symptoms="内存使用率达到98%",
            logs=["ERROR: OutOfMemoryError"],
            stack_traces=["java.lang.OutOfMemoryError"],
            resolution="优化SQL查询",
        )

        assert info.symptoms == "内存使用率达到98%"
        assert len(info.logs) == 1

    def test_task_info_with_resolve_time(self):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="closed",
            priority="medium",
            create_time=datetime(2024, 1, 1),
            resolve_time=datetime(2024, 1, 2),
        )

        assert task.resolve_time is not None

    def test_task_info_with_development(self):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            priority="low",
            create_time=datetime(2024, 1, 1),
            development={
                "commits": [],
                "code_reviews": [],
            },
        )

        assert task.development is not None

    def test_task_info_with_production(self):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            priority="low",
            create_time=datetime(2024, 1, 1),
            production={
                "incident_time": datetime(2024, 1, 1),
                "symptoms": "Test symptom",
                "logs": [],
            },
        )

        assert task.production is not None

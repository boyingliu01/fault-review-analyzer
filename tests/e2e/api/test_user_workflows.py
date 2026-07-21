"""API 用户工作流 E2E 测试 — 模拟真实 API 调用。

这些测试模拟 API 消费者的完整操作链路：
- POST /analyze → 分析任务 → 验证响应结构
- POST /analyze/batch → 批量分析 → 验证响应结构
- GET /reports/{task_id} → 获取报告 → 验证内容
- POST /feedback → 提交反馈 → 验证存储

核心原则：使用真实 FastAPI 应用 + 真实 Pipeline + 预填充缓存。
唯一的外部依赖（API 服务器）通过预填充缓存来绕过。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_config_manager
from src.api.server import create_app
from src.cache.manager import CacheManager
from src.config.manager import ConfigManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_task_data() -> dict:
    """模拟真实 API 返回的任务数据。"""
    return {
        "task_id": 70001,
        "title": "微服务网关超时导致级联故障",
        "description": "API 网关在高负载时超时",
        "status": "resolved",
        "priority": "critical",
        "create_time": "2024-07-01T08:00:00",
        "resolve_time": "2024-07-01T16:00:00",
        "development": {
            "commits": [
                {
                    "commit_id": "def456",
                    "message": "优化网关超时配置",
                    "author": "dev1",
                    "time": "2024-07-01T14:00:00",
                    "changes": ["gateway/config.yml"],
                }
            ],
            "code_changes": [],
            "code_reviews": [],
        },
        "production": {
            "incident_time": "2024-07-01T09:30:00",
            "symptoms": "API 响应超时，下游服务级联失败",
            "logs": ["ERROR: Gateway timeout", "WARN: Circuit breaker open"],
            "stack_traces": [],
            "resolution": "调整超时时间并增加熔断机制",
            "timeline": [
                {
                    "time": "2024-07-01T09:30:00",
                    "action": "发现故障",
                    "actor": "monitoring",
                    "details": "超时告警",
                }
            ],
        },
    }


@pytest.fixture
def test_env(tmp_path: Path, sample_task_data: dict) -> tuple[Path, Path]:
    """创建测试环境：缓存数据库 + 配置文件。"""
    # 创建预填充缓存
    db_path = tmp_path / "cache.db"
    cache = CacheManager(db_path=db_path, ttl=3600)
    cache.save_task(sample_task_data["task_id"], sample_task_data)

    # 创建配置文件
    config_path = tmp_path / "config.yaml"
    cache_db = str(db_path).replace("\\", "/")
    output_dir = str(tmp_path / "output").replace("\\", "/")
    config_path.write_text(
        f"""\
api:
  base_url: "https://example.com"
  timeout: 30
  retry: 3
  api_key: "test-token"
llm:
  provider: "openai"
  model: "gpt-4"
  api_key: ""
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: ""
clustering:
  algorithm: "hdbscan"
  min_cluster_size: 3
  min_samples: 2
  metric: "cosine"
cache:
  db_path: "{cache_db}"
  ttl: 3600
  enabled: true
output:
  directory: "{output_dir}"
""",
        encoding="utf-8",
    )
    return config_path, db_path


@pytest.fixture
def client(test_env: tuple[Path, Path]) -> TestClient:
    """创建配置好的 FastAPI TestClient。"""
    config_path, _ = test_env
    app = create_app(valid_tokens=None, rate_limit_requests=100)

    # 覆盖依赖，使用测试配置
    def override_config_manager() -> ConfigManager:
        cm = ConfigManager(config_path)
        cm.load()
        return cm

    app.dependency_overrides[get_config_manager] = override_config_manager
    return TestClient(app)


# ---------------------------------------------------------------------------
# 工作流 1: API 消费者分析单个任务
# 模拟: POST /analyze { task_id: 70001, options: { use_cache: true } }
# ---------------------------------------------------------------------------

class TestAnalyzeWorkflow:
    """POST /analyze 完整工作流。"""

    def test_analyze_returns_completed_status(self, client: TestClient):
        """分析缓存中的任务应返回 completed 状态。"""
        response = client.post(
            "/analyze",
            json={
                "task_id": 70001,
                "options": {
                    "use_cache": True,
                    "use_llm": False,
                    "generate_labels": False,
                    "analyze_root_cause": False,
                    "check_rules": True,
                    "generate_report": True,
                },
            },
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200, f"Unexpected status: {response.status_code}\n{response.text}"
        data = response.json()
        assert data["status"] == "completed"
        assert data["task_id"] == "70001"

    def test_analyze_response_has_expected_fields(self, client: TestClient):
        """分析响应应包含所有预期字段。"""
        response = client.post(
            "/analyze",
            json={"task_id": 70001, "options": {"use_cache": True, "use_llm": False}},
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200
        data = response.json()

        # 验证响应结构
        assert "task_id" in data
        assert "status" in data
        assert "error" in data
        assert "violations" in data
        assert "report" in data

        # 成功时 error 应为空
        assert data["error"] == ""

    def test_analyze_generates_report_content(self, client: TestClient):
        """分析应生成非空的报告内容。"""
        response = client.post(
            "/analyze",
            json={
                "task_id": 70001,
                "options": {"use_cache": True, "use_llm": False, "generate_report": True},
            },
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"], "Report should not be empty"
        assert len(data["report"]) > 50, "Report seems too short"

    def test_analyze_nonexistent_task_returns_failed(self, client: TestClient):
        """分析不存在的任务应返回 failed 状态。"""
        response = client.post(
            "/analyze",
            json={"task_id": 99999, "options": {"use_cache": True, "use_llm": False}},
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200  # API 本身成功了，但任务失败
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"], "Should have error message for missing task"


# ---------------------------------------------------------------------------
# 工作流 2: API 消费者批量分析
# 模拟: POST /analyze/batch { task_ids: [70001, 99999] }
# ---------------------------------------------------------------------------

class TestBatchAnalyzeWorkflow:
    """POST /analyze/batch 完整工作流。"""

    def test_batch_analyze_mixed_results(self, client: TestClient):
        """批量分析应返回每个任务的结果（成功+失败混合）。"""
        response = client.post(
            "/analyze/batch",
            json={
                "task_ids": [70001, 99999],
                "options": {"use_cache": True, "use_llm": False},
            },
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200
        data = response.json()

        # 验证响应结构
        assert "total_requested" in data
        assert "total_completed" in data
        assert "total_failed" in data
        assert "results" in data

        assert data["total_requested"] == 2
        # 应该有一个成功一个失败
        assert data["total_completed"] >= 1
        assert data["total_failed"] >= 1

    def test_batch_analyze_response_per_task(self, client: TestClient):
        """批量分析的每个结果应有正确的任务 ID 和状态。"""
        response = client.post(
            "/analyze/batch",
            json={
                "task_ids": [70001],
                "options": {"use_cache": True, "use_llm": False},
            },
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["task_id"] == "70001"
        assert data["results"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# 工作流 3: API 消费者获取报告
# 模拟: GET /reports/70001
# ---------------------------------------------------------------------------

class TestReportWorkflow:
    """GET /reports/{task_id} 完整工作流。"""

    def test_get_report_returns_content(self, client: TestClient):
        """获取报告应返回非空内容。"""
        response = client.get(
            "/reports/70001",
            params={"format": "markdown", "use_cache": True},
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 200, f"Unexpected status: {response.status_code}\n{response.text}"
        data = response.json()
        assert data["task_id"] == "70001"
        assert data["content"], "Report content should not be empty"
        assert len(data["content"]) > 50

    def test_get_report_invalid_format(self, client: TestClient):
        """无效格式应返回 400。"""
        response = client.get(
            "/reports/70001",
            params={"format": "invalid"},
            headers={"X-API-Token": "any"},
        )

        assert response.status_code == 400

import gc
from datetime import datetime

import pytest

from src.api.models import CommitInfo, DevelopmentInfo, ProductionInfo, TaskInfo
from src.config.manager import ConfigManager
from src.preprocessor.processor import DataPreprocessor

# Disable .env file loading globally for all tests to prevent env leakage.
# Production code leaves LOAD_ENV_FILE=True; tests flip it off.
ConfigManager.LOAD_ENV_FILE = False

# All env vars that ConfigManager._apply_env_overrides() reads
_CONFIG_ENV_VARS = [
    "API_BASE_URL",
    "API_TIMEOUT",
    "API_RETRY",
    "DEVCLOUD_TOKEN",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_BASE_URL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_BATCH_SIZE",
    "CLUSTERING_ALGORITHM",
    "CLUSTERING_MIN_CLUSTER_SIZE",
    "CLUSTERING_MIN_SAMPLES",
    "CLUSTERING_METRIC",
    "CACHE_ENABLED",
    "CACHE_TTL",
    "CACHE_STORAGE",
    "CACHE_DB_PATH",
    "RULES_BUILTIN_ENABLED",
    "OUTPUT_FORMAT",
    "OUTPUT_DIRECTORY",
    "LOG_LEVEL",
    "LOG_FILE",
]


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all config-related env vars before each test to prevent .env leakage."""
    for var in _CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def temp_dir(tmp_path):
    yield tmp_path
    gc.collect()


@pytest.fixture
def preprocessor():
    return DataPreprocessor()


@pytest.fixture
def sample_task():
    return TaskInfo(
        task_id=12345,
        title="SQL查询导致OOM",
        description="生产环境执行大表查询时发生内存溢出",
        status="resolved",
        priority="high",
        create_time=datetime(2024, 1, 15, 10, 0, 0),
        resolve_time=datetime(2024, 1, 15, 12, 0, 0),
        development=DevelopmentInfo(
            commits=[
                CommitInfo(
                    commit_id="abc123",
                    message="添加查询功能",
                    author="developer",
                    time=datetime(2024, 1, 15, 9, 0, 0),
                    changes=["src/query.py", "src/db.py"],
                )
            ]
        ),
        production=ProductionInfo(
            incident_time=datetime(2024, 1, 15, 11, 30, 0),
            symptoms="内存使用率达到98%",
            logs=["ERROR: OutOfMemoryError"],
            stack_traces=["java.lang.OutOfMemoryError"],
            resolution="优化SQL查询",
        ),
    )


@pytest.fixture
def sample_task_data():
    return {
        "task_id": 12345,
        "title": "SQL查询导致OOM",
        "description": "生产环境执行大表查询时发生内存溢出",
        "status": "resolved",
        "priority": "high",
        "create_time": "2024-01-15T10:00:00",
        "resolve_time": "2024-01-15T12:00:00",
        "development": {
            "commits": [
                {
                    "commit_id": "abc123",
                    "message": "添加查询功能",
                    "time": "2024-01-15T09:00:00",
                    "changes": ["src/query.py", "src/db.py"],
                }
            ]
        },
        "production": {
            "incident_time": "2024-01-15T11:30:00",
            "symptoms": "内存使用率达到98%",
            "logs": ["ERROR: OutOfMemoryError", "Query execution timeout"],
            "stack_traces": ["java.lang.OutOfMemoryError at QueryExecutor.execute"],
            "resolution": "优化SQL查询，添加分页",
        },
    }

"""Config test fixtures - isolates unit tests from .env leakage."""


import pytest

# All env vars that ConfigManager._apply_env_overrides() reads
_CONFIG_ENV_VARS = [
    "API_BASE_URL", "API_TIMEOUT", "API_RETRY", "DEVCLOUD_TOKEN",
    "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS", "LLM_BASE_URL",
    "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL", "EMBEDDING_BATCH_SIZE",
    "CLUSTERING_ALGORITHM", "CLUSTERING_MIN_CLUSTER_SIZE",
    "CLUSTERING_MIN_SAMPLES", "CLUSTERING_METRIC",
    "CACHE_ENABLED", "CACHE_TTL", "CACHE_STORAGE", "CACHE_DB_PATH",
    "RULES_BUILTIN_ENABLED",
    "OUTPUT_FORMAT", "OUTPUT_DIRECTORY",
    "LOG_LEVEL", "LOG_FILE",
]


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all config-related env vars before each test to prevent .env leakage."""
    for var in _CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

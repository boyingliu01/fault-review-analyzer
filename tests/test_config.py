import os
from unittest.mock import patch

import pytest

from src.config.manager import ConfigManager, ConfigValidationError
from src.config.models import (
    APIConfig,
    CacheConfig,
    ClusteringConfig,
    EmbeddingConfig,
    LLMConfig,
    LoggingConfig,
    OutputConfig,
    RulesConfig,
)

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


class TestConfigModels:
    def test_api_config_defaults(self):
        config = APIConfig()
        assert config.base_url == ""
        assert config.timeout == 30
        assert config.retry == 3

    def test_api_config_custom(self):
        config = APIConfig(
            base_url="https://api.example.com",
            timeout=60,
            retry=5,
        )
        assert config.base_url == "https://api.example.com"
        assert config.timeout == 60
        assert config.retry == 5

    def test_llm_config_defaults(self):
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.2
        assert config.max_tokens == 4096

    def test_llm_config_custom(self):
        config = LLMConfig(
            provider="qwen",
            model="qwen-max",
            temperature=0.5,
            max_tokens=8192,
        )
        assert config.provider == "qwen"
        assert config.model == "qwen-max"
        assert config.temperature == 0.5
        assert config.max_tokens == 8192

    def test_embedding_config_defaults(self):
        config = EmbeddingConfig()
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"

    def test_clustering_config_defaults(self):
        config = ClusteringConfig()
        assert config.algorithm == "hdbscan"
        assert config.min_cluster_size == 5
        assert config.min_samples == 3
        assert config.metric == "cosine"

    def test_cache_config_defaults(self):
        config = CacheConfig()
        assert config.enabled is True
        assert config.ttl == 86400
        assert config.storage == "sqlite"

    def test_rules_config_defaults(self):
        config = RulesConfig()
        assert config.builtin_enabled is True
        assert config.custom_paths == []

    def test_output_config_defaults(self):
        config = OutputConfig()
        assert config.format == "markdown"
        assert config.directory == "./output/"

    def test_logging_config_defaults(self):
        config = LoggingConfig()
        assert config.level == "INFO"


class TestConfigManager:
    @pytest.fixture(autouse=True)
    def _isolate_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clear all config-related env vars to prevent .env leakage into unit tests."""
        for var in _CONFIG_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

    def test_load_config_from_yaml(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
  timeout: 60
llm:
  provider: "qwen"
  model: "qwen-max"
"""
        )
        manager = ConfigManager(config_path=config_file)
        config = manager.load()

        assert config.api.base_url == "https://api.example.com"
        assert config.api.timeout == 60
        assert config.llm.provider == "qwen"
        assert config.llm.model == "qwen-max"

    def test_env_override_config(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
llm:
  api_key: "default-key"
"""
        )

        with patch.dict(
            os.environ,
            {
                "API_BASE_URL": "https://override.example.com",
                "LLM_API_KEY": "override-key",
            },
        ):
            manager = ConfigManager(config_path=config_file)
            config = manager.load()

            assert config.api.base_url == "https://override.example.com"
            assert config.llm.api_key == "override-key"

    def test_config_validation_invalid_timeout(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  timeout: -1
"""
        )
        manager = ConfigManager(config_path=config_file)

        with pytest.raises(ConfigValidationError):
            manager.load()

    def test_config_validation_invalid_temperature(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
llm:
  temperature: 2.0
"""
        )
        manager = ConfigManager(config_path=config_file)

        with pytest.raises(ConfigValidationError):
            manager.load()

    def test_get_config_value(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
llm:
  provider: "openai"
  model: "gpt-4"
"""
        )
        manager = ConfigManager(config_path=config_file)
        manager.load()

        assert manager.get("llm.provider") == "openai"
        assert manager.get("llm.model") == "gpt-4"
        assert manager.get("nonexistent.key", "default") == "default"

    def test_set_config_value(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
llm:
  provider: "openai"
"""
        )
        manager = ConfigManager(config_path=config_file)
        manager.load()
        manager.set("llm.model", "gpt-3.5-turbo")

        assert manager.get("llm.model") == "gpt-3.5-turbo"

    def test_save_config(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
"""
        )
        manager = ConfigManager(config_path=config_file)
        manager.load()
        manager.set("llm.provider", "qwen")
        manager.save()

        manager2 = ConfigManager(config_path=config_file)
        config = manager2.load()
        assert config.llm.provider == "qwen"

    def test_default_config_when_file_not_exists(self, temp_dir):
        nonexistent_file = temp_dir / "nonexistent.yaml"
        manager = ConfigManager(config_path=nonexistent_file)
        config = manager.load(validate=False)

        assert config.llm.provider == "openai"
        assert config.cache.enabled is True

    def test_config_property(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
"""
        )
        manager = ConfigManager(config_path=config_file)
        manager.load()  # Ensure config is loaded
        config_dict = manager.config
        assert config_dict["api"]["base_url"] == "https://api.example.com"

    def test_get_config_method(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
"""
        )
        manager = ConfigManager(config_path=config_file)
        config = manager.get_config()
        assert config.api.base_url == "https://api.example.com"

    def test_config_with_missing_api_key_warning(self, temp_dir, caplog):
        import logging

        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
"""
        )
        manager = ConfigManager(config_path=config_file)
        with caplog.at_level(logging.WARNING):
            config = manager.load()
        assert config.api.base_url == "https://api.example.com"

    def test_set_nested_config_value(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
"""
        )
        manager = ConfigManager(config_path=config_file)
        manager.load()
        manager.set("cache.ttl", 3600)
        assert manager.get("cache.ttl") == 3600

    def test_load_config_with_all_sections(self, temp_dir):
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
api:
  base_url: "https://api.example.com"
  api_key: "test-key"
  timeout: 30
  retry: 3
llm:
  provider: "openai"
  model: "gpt-4"
  api_key: "llm-key"
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
clustering:
  algorithm: "hdbscan"
  min_cluster_size: 5
cache:
  enabled: true
  ttl: 86400
rules:
  builtin_enabled: true
output:
  format: "markdown"
  directory: "./output"
logging:
  level: "DEBUG"
"""
        )
        manager = ConfigManager(config_path=config_file)
        config = manager.load()

        assert config.api.base_url == "https://api.example.com"
        assert config.llm.provider == "openai"
        assert config.embedding.provider == "openai"
        assert config.clustering.algorithm == "hdbscan"
        assert config.cache.enabled is True
        assert config.rules.builtin_enabled is True
        assert config.output.format == "markdown"
        assert config.logging.level == "DEBUG"

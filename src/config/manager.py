import os
from pathlib import Path
from typing import Any

import yaml

from src.config.models import AppConfig


class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path("config.yaml")
        self.config_path = config_path
        self._config: AppConfig | None = None
        self._env_prefix_map = {
            "API_BASE_URL": ("api", "base_url"),
            "API_TIMEOUT": ("api", "timeout"),
            "API_RETRY": ("api", "retry"),
            "API_API_KEY": ("api", "api_key"),
            "API_TOKEN": ("api", "api_key"),
            "LLM_PROVIDER": ("llm", "provider"),
            "LLM_MODEL": ("llm", "model"),
            "LLM_API_KEY": ("llm", "api_key"),
            "LLM_TEMPERATURE": ("llm", "temperature"),
            "LLM_MAX_TOKENS": ("llm", "max_tokens"),
            "LLM_BASE_URL": ("llm", "base_url"),
            "EMBEDDING_PROVIDER": ("embedding", "provider"),
            "EMBEDDING_MODEL": ("embedding", "model"),
            "EMBEDDING_API_KEY": ("embedding", "api_key"),
            "EMBEDDING_BASE_URL": ("embedding", "base_url"),
            "EMBEDDING_BATCH_SIZE": ("embedding", "batch_size"),
            "CLUSTERING_ALGORITHM": ("clustering", "algorithm"),
            "CLUSTERING_MIN_CLUSTER_SIZE": ("clustering", "min_cluster_size"),
            "CLUSTERING_MIN_SAMPLES": ("clustering", "min_samples"),
            "CLUSTERING_METRIC": ("clustering", "metric"),
            "CACHE_ENABLED": ("cache", "enabled"),
            "CACHE_TTL": ("cache", "ttl"),
            "CACHE_STORAGE": ("cache", "storage"),
            "CACHE_DB_PATH": ("cache", "db_path"),
            "RULES_BUILTIN_ENABLED": ("rules", "builtin_enabled"),
            "OUTPUT_FORMAT": ("output", "format"),
            "OUTPUT_DIRECTORY": ("output", "directory"),
            "LOG_LEVEL": ("logging", "level"),
            "LOG_FILE": ("logging", "file"),
        }

    def load(self, validate: bool = True) -> AppConfig:
        config_dict = self._load_from_file()
        self._apply_env_overrides(config_dict)
        self._config = AppConfig(**config_dict)
        if validate:
            self._validate_config()
        return self._config

    def _validate_config(self) -> None:
        """Validate required configuration fields."""
        if self._config is None:
            raise ValueError("Configuration not loaded")
        if not self._config.api.base_url:
            raise ValueError(
                "API base_url is required. Please set it in config.yaml or via "
                "API_BASE_URL environment variable. See .env.example for reference."
            )
        if not self._config.api.api_key:
            import logging
            logging.warning(
                "API API key not configured. Set via API_API_KEY env var or config.yaml. "
                "API calls will fail without authentication."
            )

    def _load_from_file(self) -> dict[str, Any]:
        if self.config_path and self.config_path.exists():
            with self.config_path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> None:
        for env_key, (section, field) in self._env_prefix_map.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section][field] = self._parse_env_value(env_value)

    def _parse_env_value(self, value: str) -> Any:
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if self._config is None:
            self.load()

        parts = key.split(".")
        obj: Any = self._config

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default

        return obj

    def set(self, key: str, value: Any) -> None:
        if self._config is None:
            self.load()

        parts = key.split(".")
        obj: Any = self._config

        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                raise KeyError(f"Invalid config key: {key}")

        if hasattr(obj, parts[-1]):
            setattr(obj, parts[-1], value)
        else:
            raise KeyError(f"Invalid config key: {key}")

    def save(self) -> None:
        if self._config is None:
            return

        if self.config_path is None:
            return

        config_dict = self._config.model_dump()

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            return self.load()
        return self._config

    def get_config(self) -> AppConfig:
        return self.config

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.config.models import AppConfig


class ConfigValidationError(Exception):
    """Configuration validation error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigNotFoundError(Exception):
    """Configuration file not found error."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Configuration file not found: {path}")


class ConfigKeyError(Exception):
    """Configuration key not found error."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Configuration key not found: {key}")


class ConfigManager:
    DEFAULT_CONFIG_PATH = Path("config/config.yaml")

    def __init__(
        self,
        config_path: Path | str | None = None,
        config_file: str | None = None,
        config: dict[str, Any] | None = None,
        defaults: dict[str, Any] | None = None,
    ):
        # Handle both config_path and config_file parameters
        if config_file is not None:
            self.config_path = Path(config_file)
        elif config_path is None:
            self.config_path = None
        elif isinstance(config_path, str):
            self.config_path = Path(config_path)
        else:
            self.config_path = config_path

        self._default_config = deepcopy(defaults) if defaults else {}
        self._config: dict[str, Any] = deepcopy(config) if config else {}
        self._app_config: AppConfig | None = None

        # If no initial config but we have defaults, use defaults
        if not self._config and self._default_config:
            self._config = deepcopy(self._default_config)

        # Load from file if path exists and no initial config
        if not config and self.config_path and self.config_path.exists():
            self.load_from_file(str(self.config_path))

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def config_file(self) -> str | None:
        return str(self.config_path) if self.config_path else None

    def load_from_file(self, path: str, merge: bool = False) -> None:
        """Load configuration from a file (YAML or JSON)."""
        file_path = Path(path)
        if not file_path.exists():
            raise ConfigNotFoundError(path)

        with file_path.open(encoding="utf-8") as f:
            if file_path.suffix.lower() == ".json":
                loaded_config = json.load(f)
            else:
                loaded_config = yaml.safe_load(f) or {}

        if merge:
            self.merge(loaded_config, overwrite=True)
        else:
            self._config = loaded_config

        self._app_config = None
        self.config_path = file_path

    def save_to_file(self, path: str) -> None:
        """Save configuration to a file (YAML or JSON)."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("w", encoding="utf-8") as f:
            if file_path.suffix.lower() == ".json":
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            else:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)

    def save(self) -> None:
        """Save configuration to the current config file."""
        if self.config_path:
            self.save_to_file(str(self.config_path))

    def get(self, key: str, default: Any = ...) -> Any:
        """Get a configuration value by dot-separated key."""
        parts = key.split(".")
        obj = self._config

        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                if default is ...:
                    raise ConfigKeyError(key)
                return default

        return obj

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dot-separated key."""
        parts = key.split(".")
        obj = self._config

        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]

        obj[parts[-1]] = value
        self._app_config = None

    def merge(self, config: dict[str, Any], overwrite: bool = False) -> None:
        """Merge a configuration dictionary into the current configuration."""
        self._deep_merge(self._config, config, overwrite)
        self._app_config = None

    def _deep_merge(
        self, target: dict[str, Any], source: dict[str, Any], overwrite: bool
    ) -> None:
        """Deep merge source into target."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value, overwrite)
            elif overwrite or key not in target:
                target[key] = deepcopy(value)

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the configuration."""
        errors: list[str] = []

        try:
            # Try to create AppConfig to validate
            config_dict = deepcopy(self._config)
            self._apply_env_overrides(config_dict)
            AppConfig(**config_dict)
        except Exception as e:
            errors.append(str(e))

        return len(errors) == 0, errors

    def reset(self) -> None:
        """Reset configuration to defaults or empty state."""
        if self._default_config:
            self._config = deepcopy(self._default_config)
        else:
            self._config = {}
        self._app_config = None

    def _get_app_config(self) -> AppConfig:
        """Get or create AppConfig instance from current config."""
        if self._app_config is None:
            config_dict = deepcopy(self._config)
            self._apply_env_overrides(config_dict)
            self._app_config = AppConfig(**config_dict)
        return self._app_config

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> None:
        """Apply environment variable overrides to config dict."""
        env_prefix_map = {
            "API_BASE_URL": ("api", "base_url"),
            "API_TIMEOUT": ("api", "timeout"),
            "API_RETRY": ("api", "retry"),
            "DEVCLOUD_TOKEN": ("api", "api_key"),
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

        for env_key, (section, field) in env_prefix_map.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section][field] = self._parse_env_value(env_value)

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
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

    def load(self, validate: bool = True) -> AppConfig:
        """Load and return AppConfig instance."""
        if self.config_path and self.config_path.exists() and not self._config:
            self.load_from_file(str(self.config_path))

        try:
            app_config = self._get_app_config()
        except Exception as e:
            if validate:
                raise ConfigValidationError("Configuration validation failed", {"errors": [str(e)]})
            else:
                raise

        return app_config

    @property
    def app_config(self) -> AppConfig:
        """Get AppConfig instance."""
        return self._get_app_config()

    def get_config(self) -> AppConfig:
        """Get AppConfig instance (alias for backward compatibility)."""
        return self.app_config

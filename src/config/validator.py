"""Configuration validator module.

This module provides comprehensive validation for the application configuration,
checking the integrity and validity of all configuration sections including:
- API configuration
- LLM configuration
- Embedding configuration
- Database configuration
"""

from typing import Any

from loguru import logger


class ConfigValidator:
    """Validates application configuration from raw dict data."""

    def validate_dict(self, config_dict: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate the complete configuration from a dictionary.

        Args:
            config_dict: Configuration dictionary to validate

        Returns:
            tuple[bool, list[str]]: (is_valid, errors)
        """
        errors: list[str] = []

        # Validate each configuration section
        api_config = config_dict.get("api", {})
        llm_config = config_dict.get("llm", {})
        embedding_config = config_dict.get("embedding", {})
        cache_config = config_dict.get("cache", {})

        api_errors = self._validate_api_config_dict(api_config)
        llm_errors = self._validate_llm_config_dict(llm_config)
        embedding_errors = self._validate_embedding_config_dict(embedding_config)
        cache_errors = self._validate_cache_config_dict(cache_config)

        errors.extend(api_errors)
        errors.extend(llm_errors)
        errors.extend(embedding_errors)
        errors.extend(cache_errors)

        if errors:
            logger.warning(f"Configuration validation failed with {len(errors)} errors")
            return False, errors

        logger.debug("Configuration validation passed")
        return True, []

    def _validate_api_config_dict(self, api_config: dict[str, Any]) -> list[str]:
        """Validate API configuration from dict.

        Args:
            api_config: API configuration dictionary

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        base_url = api_config.get("base_url", "")
        if not base_url:
            errors.append("API base URL is required")
        elif not base_url.startswith(("http://", "https://")):
            errors.append("API base URL must start with http:// or https://")

        if not api_config.get("api_key", ""):
            errors.append("API key is required")

        timeout = api_config.get("timeout", 30)
        if timeout <= 0:
            errors.append(f"API timeout must be > 0, got {timeout}")

        retry = api_config.get("retry", 3)
        if retry < 0:
            errors.append(f"API retry count must be >= 0, got {retry}")

        api_path_prefix = api_config.get("api_path_prefix", "")
        if not api_path_prefix:
            errors.append("API path prefix is required")
        elif not api_path_prefix.startswith("/"):
            errors.append("API path prefix must start with /")

        return errors

    def _validate_llm_config_dict(self, llm_config: dict[str, Any]) -> list[str]:
        """Validate LLM configuration from dict.

        Args:
            llm_config: LLM configuration dictionary

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        if not llm_config.get("model", ""):
            errors.append("LLM model is required")

        if not llm_config.get("api_key", ""):
            errors.append("LLM API key is required")

        temperature = llm_config.get("temperature", 0.7)
        if not (0.0 <= temperature <= 1.0):
            errors.append(f"LLM temperature must be between 0.0 and 1.0, got {temperature}")

        max_tokens = llm_config.get("max_tokens", 4096)
        if max_tokens <= 0:
            errors.append(f"LLM max tokens must be > 0, got {max_tokens}")

        base_url = llm_config.get("base_url", "")
        if base_url and not base_url.startswith(("http://", "https://")):
            errors.append("LLM base URL must start with http:// or https://")

        return errors

    def _validate_embedding_config_dict(self, embedding_config: dict[str, Any]) -> list[str]:
        """Validate embedding configuration from dict.

        Args:
            embedding_config: Embedding configuration dictionary

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        provider = embedding_config.get("provider", "openai")
        allowed_providers = [
            "openai",
            "bge",
            "m3e",
            "codebert",
            "zhipu",
            "local",
            "volcengine",
            "custom",
            "whalecloud",
            "sentence-transformers",
        ]
        if provider not in allowed_providers:
            errors.append(
                f"Embedding provider must be one of {', '.join(allowed_providers)}, got {provider}"
            )

        if not embedding_config.get("model", ""):
            errors.append("Embedding model is required")

        if provider != "local" and not embedding_config.get("api_key", ""):
            errors.append("Embedding API key is required for non-local providers")

        batch_size = embedding_config.get("batch_size", 100)
        if batch_size <= 0:
            errors.append(f"Embedding batch size must be > 0, got {batch_size}")

        base_url = embedding_config.get("base_url", "")
        if base_url and not base_url.startswith(("http://", "https://")):
            errors.append("Embedding base URL must start with http:// or https://")

        return errors

    def _validate_cache_config_dict(self, cache_config: dict[str, Any]) -> list[str]:
        """Validate cache configuration from dict.

        Args:
            cache_config: Cache configuration dictionary

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        storage = cache_config.get("storage", "sqlite")
        allowed_storage = ["sqlite", "file", "memory"]
        if storage not in allowed_storage:
            errors.append(
                f"Cache storage must be one of {', '.join(allowed_storage)}, got {storage}"
            )

        ttl = cache_config.get("ttl", 86400)
        if ttl < 0:
            errors.append(f"Cache TTL must be >= 0, got {ttl}")

        if storage in ["sqlite", "file"] and not cache_config.get("db_path", ""):
            errors.append("Cache database path is required for sqlite or file storage")

        return errors

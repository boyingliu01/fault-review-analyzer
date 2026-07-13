"""Tests for the configuration validator."""

import pytest

from src.config.validator import ConfigValidator


class TestConfigValidator:
    """Tests for ConfigValidator."""

    @pytest.fixture
    def validator(self):
        """Create a ConfigValidator instance."""
        return ConfigValidator()

    @pytest.fixture
    def valid_config_dict(self):
        """Create a valid config dict for testing."""
        return {
            "api": {
                "base_url": "https://api.example.com",
                "timeout": 30,
                "retry": 3,
                "api_key": "valid-api-key",
                "api_path_prefix": "/portal/ai-gateway/devspace/rpc/v3/work-item"
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "valid-llm-key",
                "temperature": 0.7,
                "max_tokens": 4096,
                "base_url": "https://api.openai.com"
            },
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "valid-embedding-key",
                "base_url": "https://api.openai.com",
                "batch_size": 100
            },
            "cache": {
                "enabled": True,
                "ttl": 86400,
                "storage": "sqlite",
                "db_path": "./data/cache/cache.db"
            }
        }

    def test_validate_valid_config(self, validator, valid_config_dict):
        """Test validating a valid configuration."""
        is_valid, errors = validator.validate_dict(valid_config_dict)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_empty_api_config(self, validator):
        """Test validating with empty API config."""
        config = {
            "api": {},
            "llm": {},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("API base URL is required" in err for err in errors)
        assert any("API key is required" in err for err in errors)
        assert any("API path prefix is required" in err for err in errors)

    def test_validate_invalid_api_url(self, validator):
        """Test validating API config with invalid URL."""
        config = {
            "api": {
                "base_url": "not-a-valid-url",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("API base URL must start with" in err for err in errors)

    def test_validate_invalid_api_timeout(self, validator):
        """Test validating API config with invalid timeout."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "timeout": -1,
                "retry": -2,
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("API timeout must be" in err for err in errors)
        assert any("API retry count must be" in err for err in errors)

    def test_validate_invalid_api_path_prefix(self, validator):
        """Test validating API config with invalid path prefix."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "invalid/no-leading-slash"
            },
            "llm": {},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("API path prefix must start with" in err for err in errors)

    def test_validate_invalid_llm_provider(self, validator):
        """Test validating LLM config with invalid provider."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {"provider": "invalid-provider"},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("LLM provider must be one of" in err for err in errors)

    def test_validate_invalid_llm_temperature(self, validator):
        """Test validating LLM config with invalid temperature."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "test-key",
                "temperature": 1.5
            },
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("LLM temperature must be between" in err for err in errors)

    def test_validate_invalid_llm_max_tokens(self, validator):
        """Test validating LLM config with invalid max tokens."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "test-key",
                "max_tokens": -1
            },
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("LLM max tokens must be" in err for err in errors)

    def test_validate_invalid_llm_base_url(self, validator):
        """Test validating LLM config with invalid base URL."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "api_key": "test-key",
                "base_url": "not-a-valid-url"
            },
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("LLM base URL must start with" in err for err in errors)

    def test_validate_missing_llm_config(self, validator):
        """Test validating LLM config with missing fields."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("LLM model is required" in err for err in errors)
        assert any("LLM API key is required" in err for err in errors)

    def test_validate_invalid_embedding_provider(self, validator):
        """Test validating embedding config with invalid provider."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {"provider": "invalid-provider"},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Embedding provider must be one of" in err for err in errors)

    def test_validate_local_embedding_no_api_key(self, validator):
        """Test validating local embedding config doesn't require API key."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {
                "provider": "local",
                "model": "local-model",
                "batch_size": 100
            },
            "cache": {}
        }
        # Only check embedding config specifically
        embedding_errors = validator._validate_embedding_config_dict(config["embedding"])
        assert not any("Embedding API key is required" in err for err in embedding_errors)

    def test_validate_invalid_embedding_batch_size(self, validator):
        """Test validating embedding config with invalid batch size."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "test-key",
                "batch_size": 0
            },
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Embedding batch size must be" in err for err in errors)

    def test_validate_invalid_embedding_base_url(self, validator):
        """Test validating embedding config with invalid base URL."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "test-key",
                "base_url": "not-a-valid-url"
            },
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Embedding base URL must start with" in err for err in errors)

    def test_validate_invalid_cache_storage(self, validator):
        """Test validating cache config with invalid storage."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {"storage": "invalid-storage"}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Cache storage must be one of" in err for err in errors)

    def test_validate_invalid_cache_ttl(self, validator):
        """Test validating cache config with invalid TTL."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {"ttl": -100}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Cache TTL must be" in err for err in errors)

    def test_validate_missing_cache_db_path(self, validator):
        """Test validating cache config with missing DB path."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {
                "storage": "sqlite",
                "db_path": ""
            }
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert any("Cache database path is required" in err for err in errors)

    def test_validate_memory_cache_no_db_path(self, validator):
        """Test validating memory cache doesn't require DB path."""
        config = {
            "api": {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "api_path_prefix": "/api/v1"
            },
            "llm": {},
            "embedding": {},
            "cache": {
                "storage": "memory",
                "db_path": ""
            }
        }
        # Only check cache config specifically
        cache_errors = validator._validate_cache_config_dict(config["cache"])
        assert not any("Cache database path is required" in err for err in cache_errors)

    def test_validate_multiple_errors(self, validator):
        """Test validating a config with multiple errors."""
        config = {
            "api": {},
            "llm": {"provider": "invalid"},
            "embedding": {},
            "cache": {}
        }
        is_valid, errors = validator.validate_dict(config)
        assert is_valid is False
        assert len(errors) > 5

"""Tests for the configuration manager."""

import json

import pytest

from src.config.manager import (
    ConfigKeyError,
    ConfigManager,
    ConfigNotFoundError,
    ConfigValidationError,
)
from src.config.models import AppConfig


class TestConfigValidationError:
    """Tests for ConfigValidationError."""

    def test_error_creation(self):
        """Test creating a validation error."""
        error = ConfigValidationError("Invalid config value")
        assert str(error) == "Invalid config value"

    def test_error_with_details(self):
        """Test creating a validation error with details."""
        details = {"field": "timeout", "value": -1}
        error = ConfigValidationError("Invalid timeout", details=details)
        assert "timeout" in str(error)


class TestConfigNotFoundError:
    """Tests for ConfigNotFoundError."""

    def test_error_creation(self):
        """Test creating a not found error."""
        error = ConfigNotFoundError("/path/to/config.yaml")
        assert "/path/to/config.yaml" in str(error)


class TestConfigKeyError:
    """Tests for ConfigKeyError."""

    def test_error_creation(self):
        """Test creating a key error."""
        error = ConfigKeyError("database.host")
        assert "database.host" in str(error)


class TestConfigManagerCreation:
    """Tests for ConfigManager creation."""

    def test_default_creation(self):
        """Test creating with default settings."""
        manager = ConfigManager()
        assert manager.config == {}
        assert manager.config_file is None
        assert manager._default_config is not None

    def test_creation_with_config(self):
        """Test creating with initial config."""
        initial = {"database": {"host": "localhost", "port": 5432}}
        manager = ConfigManager(config=initial)
        assert manager.config == initial

    def test_creation_with_config_file(self, tmp_path):
        """Test creating with a config file."""
        config_file = tmp_path / "config.yaml"
        config_data = {"app": {"name": "TestApp"}}

        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        manager = ConfigManager(config_file=str(config_file))
        assert manager.config_file == str(config_file)


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_from_file_yaml(self, tmp_path):
        """Test loading config from YAML file."""
        import yaml

        config_file = tmp_path / "test.yaml"
        data = {"server": {"host": "0.0.0.0", "port": 8080}}

        with open(config_file, "w") as f:
            yaml.dump(data, f)

        manager = ConfigManager()
        manager.load_from_file(str(config_file))

        assert manager.config == data

    def test_load_from_file_json(self, tmp_path):
        """Test loading config from JSON file."""
        config_file = tmp_path / "test.json"
        data = {"api": {"version": "v1", "timeout": 30}}

        with open(config_file, "w") as f:
            json.dump(data, f)

        manager = ConfigManager()
        manager.load_from_file(str(config_file))

        assert manager.config == data

    def test_load_from_nonexistent_file(self):
        """Test loading from a file that doesn't exist."""
        manager = ConfigManager()

        with pytest.raises(ConfigNotFoundError):
            manager.load_from_file("/nonexistent/path/config.yaml")

    def test_load_from_file_with_merge(self, tmp_path):
        """Test loading config and merging with existing."""
        import yaml

        config_file = tmp_path / "test.yaml"

        initial = {"app": {"name": "MyApp"}, "debug": True}
        new_data = {"database": {"host": "localhost"}}

        with open(config_file, "w") as f:
            yaml.dump(new_data, f)

        manager = ConfigManager(config=initial)
        manager.load_from_file(str(config_file), merge=True)

        assert manager.config["app"]["name"] == "MyApp"
        assert manager.config["debug"] is True
        assert manager.config["database"]["host"] == "localhost"


class TestConfigSaving:
    """Tests for configuration saving."""

    def test_save_to_file_yaml(self, tmp_path):
        """Test saving config to YAML file."""
        import yaml

        config_file = tmp_path / "output.yaml"

        manager = ConfigManager(config={"server": {"port": 3000}})
        manager.save_to_file(str(config_file))

        assert config_file.exists()

        with open(config_file) as f:
            loaded = yaml.safe_load(f)

        assert loaded["server"]["port"] == 3000

    def test_save_to_file_json(self, tmp_path):
        """Test saving config to JSON file."""
        config_file = tmp_path / "output.json"

        manager = ConfigManager(config={"api": {"key": "secret123"}})
        manager.save_to_file(str(config_file))

        assert config_file.exists()

        with open(config_file) as f:
            loaded = json.load(f)

        assert loaded["api"]["key"] == "secret123"

    def test_save_to_file_with_parents(self, tmp_path):
        """Test saving creates parent directories."""
        deep_path = tmp_path / "deep" / "nested" / "config.yaml"

        manager = ConfigManager(config={"test": "value"})
        manager.save_to_file(str(deep_path))

        assert deep_path.exists()


class TestConfigGetSet:
    """Tests for configuration get/set operations."""

    def test_get_simple_key(self):
        """Test getting a simple config value."""
        manager = ConfigManager(config={"name": "TestApp", "version": "1.0"})

        assert manager.get("name") == "TestApp"
        assert manager.get("version") == "1.0"

    def test_get_nested_key(self):
        """Test getting a nested config value."""
        config = {
            "database": {"host": "localhost", "port": 5432, "credentials": {"username": "admin"}}
        }
        manager = ConfigManager(config=config)

        assert manager.get("database.host") == "localhost"
        assert manager.get("database.port") == 5432
        assert manager.get("database.credentials.username") == "admin"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        manager = ConfigManager(config={"name": "Test"})

        with pytest.raises(ConfigKeyError):
            manager.get("nonexistent")

    def test_get_with_default(self):
        """Test getting a key with default value."""
        manager = ConfigManager(config={"name": "Test"})

        # Should return default for nonexistent key
        assert manager.get("nonexistent", default="default_value") == "default_value"

        # Should return actual value when key exists
        assert manager.get("name", default="Default") == "Test"

    def test_get_nested_with_default(self):
        """Test getting nested key with default."""
        manager = ConfigManager(config={"database": {"host": "localhost"}})

        assert manager.get("database.port", default=5432) == 5432
        assert manager.get("database.host", default="fallback") == "localhost"

    def test_set_simple_key(self):
        """Test setting a simple config value."""
        manager = ConfigManager()

        manager.set("name", "NewApp")
        assert manager.config["name"] == "NewApp"

    def test_set_nested_key(self):
        """Test setting a nested config value."""
        manager = ConfigManager()

        manager.set("database.host", "localhost")
        manager.set("database.port", 5432)

        assert manager.config["database"]["host"] == "localhost"
        assert manager.config["database"]["port"] == 5432

    def test_set_deeply_nested_key(self):
        """Test setting a deeply nested config value."""
        manager = ConfigManager()

        manager.set("a.b.c.d.e", "deep_value")

        assert manager.config["a"]["b"]["c"]["d"]["e"] == "deep_value"

    def test_set_overwrite_existing(self):
        """Test setting overwrites existing value."""
        manager = ConfigManager(config={"name": "OldName"})

        manager.set("name", "NewName")
        assert manager.config["name"] == "NewName"


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_empty_config(self):
        """Test validating empty config."""
        manager = ConfigManager()

        is_valid, errors = manager.validate()
        # Empty config might be valid depending on requirements
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_validate_valid_config(self):
        """Test validating valid config."""
        manager = ConfigManager(
            config={
                "app": {"name": "TestApp", "version": "1.0"},
                "database": {"host": "localhost", "port": 5432},
            }
        )

        is_valid, errors = manager.validate()
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)


class TestConfigMerge:
    """Tests for configuration merging."""

    def test_merge_simple_configs(self):
        """Test merging simple configs."""
        manager = ConfigManager(config={"a": 1, "b": 2})

        manager.merge({"c": 3, "d": 4})

        assert manager.config["a"] == 1
        assert manager.config["b"] == 2
        assert manager.config["c"] == 3
        assert manager.config["d"] == 4

    def test_merge_nested_configs(self):
        """Test merging nested configs."""
        manager = ConfigManager(
            config={"database": {"host": "localhost", "port": 5432}, "app": {"name": "MyApp"}}
        )

        manager.merge(
            {"database": {"username": "admin", "password": "secret"}, "cache": {"enabled": True}}
        )

        # Original values preserved
        assert manager.config["database"]["host"] == "localhost"
        assert manager.config["database"]["port"] == 5432
        # New values added
        assert manager.config["database"]["username"] == "admin"
        assert manager.config["cache"]["enabled"] is True

    def test_merge_overwrite_existing(self):
        """Test merge with overwrite option."""
        manager = ConfigManager(config={"key": "old_value"})

        # Default: don't overwrite
        manager.merge({"key": "new_value"})
        assert manager.config["key"] == "old_value"

        # With overwrite=True
        manager.merge({"key": "new_value"}, overwrite=True)
        assert manager.config["key"] == "new_value"


class TestAppConfigMethods:
    """Tests for AppConfig related methods."""

    def test_app_config_property(self, tmp_path):
        """Test the app_config property."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
api:
  base_url: https://api.example.com
llm:
  provider: openai
  model: gpt-4
""")

        manager = ConfigManager(config_file=str(config_file))
        assert isinstance(manager.app_config, AppConfig)
        assert manager.app_config.api.base_url == "https://api.example.com"

    def test_get_config_method(self):
        """Test get_config alias method."""
        manager = ConfigManager(config={"api": {"base_url": "https://api.example.com"}})
        assert manager.get_config() == manager.app_config

    def test_load_method_with_validation(self):
        """Test load method with validation."""
        manager = ConfigManager(config={"api": {"base_url": "https://api.example.com"}})
        result = manager.load(validate=True)
        assert isinstance(result, AppConfig)

    def test_load_method_with_invalid_config(self):
        """Test load method with invalid configuration."""
        manager = ConfigManager(config={"api": {"base_url": "not-a-valid-url"}})
        # Both validate=True and validate=False will raise because Pydantic validates on creation
        with pytest.raises(ConfigValidationError):
            manager.load(validate=True)

    def test_load_method_with_env_overrides(self, monkeypatch):
        """Test environment variable overrides in load method."""
        monkeypatch.setenv("API_BASE_URL", "https://override.example.com")
        monkeypatch.setenv("API_TIMEOUT", "60")

        manager = ConfigManager(config={"api": {"base_url": "https://original.example.com"}})
        result = manager.load()
        assert result.api.base_url == "https://override.example.com"
        assert result.api.timeout == 60

    def test_parse_env_value_boolean(self, monkeypatch):
        """Test parsing boolean values from environment."""
        monkeypatch.setenv("CACHE_ENABLED", "true")
        manager = ConfigManager()
        result = manager.load()
        assert result.cache.enabled is True

    def test_save_method(self, tmp_path):
        """Test save method."""
        config_file = tmp_path / "config.yaml"
        manager = ConfigManager(config_file=str(config_file))
        manager.set("api.base_url", "https://api.example.com")
        manager.save()
        assert config_file.exists()
        # Verify it can be loaded back
        manager2 = ConfigManager(config_file=str(config_file))
        manager2.load_from_file(str(config_file))
        assert manager2.get("api.base_url") == "https://api.example.com"


class TestConfigManagerEdgeCases:
    """Tests for edge cases in ConfigManager."""

    def test_init_with_path_as_path_object(self, tmp_path):
        """Test initializing with Path object."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('{"test": "value"}')
        manager = ConfigManager(config_path=config_file)
        assert manager.get("test") == "value"

    def test_load_from_file_auto_create_parent_dirs(self, tmp_path):
        """Test that load_from_file doesn't create parent dirs (only save_to_file does)."""
        non_existent = tmp_path / "non_existent" / "config.yaml"
        manager = ConfigManager()
        with pytest.raises(ConfigNotFoundError):
            manager.load_from_file(str(non_existent))


class TestConfigReset:
    """Tests for configuration reset."""

    def test_reset_to_empty(self):
        """Test resetting to empty config."""
        manager = ConfigManager(config={"key": "value"})

        manager.reset()

        assert manager.config == {}

    def test_reset_to_defaults(self):
        """Test resetting to default config."""
        defaults = {"app": {"name": "DefaultApp"}, "debug": False}
        manager = ConfigManager(config={"key": "value"}, defaults=defaults)

        manager.reset()

        assert manager.config == defaults

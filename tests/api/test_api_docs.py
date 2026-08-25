"""API documentation exposure policy tests."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.api.server import create_app

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def load_start_api_server() -> ModuleType:
    script_path = Path(__file__).parents[2] / "scripts" / "start_api_server.py"
    spec = importlib.util.spec_from_file_location("test_api_docs_start_server", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", _DOCS_PATHS)
def test_documentation_endpoint_is_not_found_by_default(path: str) -> None:
    # Given
    client = TestClient(create_app())

    # When
    response = client.get(path)

    # Then
    assert response.status_code == 404


@pytest.mark.parametrize("path", _DOCS_PATHS)
def test_enabled_documentation_requires_token(path: str) -> None:
    # Given
    client = TestClient(create_app(valid_tokens={"valid-token"}, api_docs_enabled=True))

    # When
    response = client.get(path)

    # Then
    assert response.status_code == 401


@pytest.mark.parametrize("path", _DOCS_PATHS)
def test_enabled_documentation_accepts_valid_token(path: str) -> None:
    # Given
    client = TestClient(create_app(valid_tokens={"valid-token"}, api_docs_enabled=True))

    # When
    response = client.get(path, headers={"X-API-Token": "valid-token"})

    # Then
    assert response.status_code == 200


@pytest.mark.parametrize("path", _DOCS_PATHS)
def test_enabled_documentation_allows_explicit_unauthenticated_mode(path: str) -> None:
    # Given
    client = TestClient(create_app(allow_unauthenticated=True, api_docs_enabled=True))

    # When
    response = client.get(path)

    # Then
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("api_docs_enabled", "advertises_docs"),
    [(False, False), (True, True)],
)
def test_root_advertises_documentation_only_when_enabled(
    api_docs_enabled: bool,
    advertises_docs: bool,
) -> None:
    # Given
    client = TestClient(create_app(allow_unauthenticated=True, api_docs_enabled=api_docs_enabled))

    # When
    response = client.get("/")

    # Then
    assert ("docs" in response.json()) is advertises_docs


@pytest.mark.parametrize(
    ("environment_value", "expected"),
    [(None, False), ("false", False), ("true", True)],
)
def test_server_main_strictly_parses_and_passes_docs_setting(
    monkeypatch: pytest.MonkeyPatch,
    environment_value: str | None,
    expected: bool,
) -> None:
    # Given
    if environment_value is None:
        monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("API_DOCS_ENABLED", environment_value)

    # When
    with patch("src.api.server.create_app") as mock_create_app, patch("uvicorn.run"):
        server.main()

    # Then
    assert mock_create_app.call_args.kwargs["api_docs_enabled"] is expected


def test_server_main_rejects_invalid_docs_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv("API_DOCS_ENABLED", "yes")

    # When / Then
    with pytest.raises(ValueError, match="API_DOCS_ENABLED"):
        server.main()


@pytest.mark.parametrize(
    ("environment_value", "expected"),
    [(None, False), ("false", False), ("true", True)],
)
def test_start_script_strictly_parses_and_passes_docs_setting(
    monkeypatch: pytest.MonkeyPatch,
    environment_value: str | None,
    expected: bool,
) -> None:
    # Given
    start_api_server = load_start_api_server()
    if environment_value is None:
        monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("API_DOCS_ENABLED", environment_value)

    # When
    with patch.object(start_api_server, "create_app") as mock_create_app, patch("uvicorn.run"):
        start_api_server.main()

    # Then
    assert mock_create_app.call_args.kwargs["api_docs_enabled"] is expected


def test_start_script_rejects_invalid_docs_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    start_api_server = load_start_api_server()
    monkeypatch.setenv("API_DOCS_ENABLED", "yes")

    # When / Then
    with pytest.raises(ValueError, match="API_DOCS_ENABLED"):
        start_api_server.main()

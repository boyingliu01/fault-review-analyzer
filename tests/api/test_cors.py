"""CORS configuration and preflight tests."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import server
from src.api.server import create_app, parse_environment_list


def load_start_api_server() -> ModuleType:
    script_path = Path(__file__).parents[2] / "scripts" / "start_api_server.py"
    spec = importlib.util.spec_from_file_location("test_start_api_server", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_environment_list_trims_and_omits_empty_values(monkeypatch):
    monkeypatch.setenv(
        "API_CORS_ORIGINS",
        " https://app.example.com, ,https://admin.example.com ",
    )

    values = parse_environment_list("API_CORS_ORIGINS")

    assert values == ("https://app.example.com", "https://admin.example.com")


def test_server_main_propagates_explicit_cors_environment_settings(monkeypatch):
    monkeypatch.setenv("API_CORS_ORIGINS", "https://app.example.com, https://admin.example.com")
    monkeypatch.setenv("API_CORS_METHODS", "GET, POST")
    monkeypatch.setenv("API_CORS_HEADERS", "Content-Type, X-API-Token")

    with (
        patch("src.api.server.create_app") as mock_create_app,
        patch("uvicorn.run"),
    ):
        server.main()

    assert mock_create_app.call_args.kwargs["allowed_origins"] == (
        "https://app.example.com",
        "https://admin.example.com",
    )
    assert mock_create_app.call_args.kwargs["allowed_methods"] == ("GET", "POST")
    assert mock_create_app.call_args.kwargs["allowed_headers"] == (
        "Content-Type",
        "X-API-Token",
    )


def test_start_script_propagates_explicit_cors_environment_settings(monkeypatch):
    start_api_server = load_start_api_server()
    monkeypatch.setenv("API_CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("API_CORS_METHODS", "GET,POST")
    monkeypatch.setenv("API_CORS_HEADERS", "Content-Type,X-API-Token")

    with (
        patch.object(start_api_server, "create_app") as mock_create_app,
        patch("uvicorn.run"),
    ):
        start_api_server.main()

    assert mock_create_app.call_args.kwargs["allowed_origins"] == ("https://app.example.com",)
    assert mock_create_app.call_args.kwargs["allowed_methods"] == ("GET", "POST")
    assert mock_create_app.call_args.kwargs["allowed_headers"] == (
        "Content-Type",
        "X-API-Token",
    )


def test_default_policy_does_not_allow_cross_origin_requests():
    client = TestClient(create_app(allow_unauthenticated=True))

    response = client.options(
        "/analyze",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-API-Token",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_preflight_allows_configured_origin_method_and_headers():
    client = TestClient(
        create_app(
            allow_unauthenticated=True,
            allowed_origins=("https://app.example.com",),
            allowed_methods=("POST",),
            allowed_headers=("Content-Type", "X-API-Token"),
        )
    )

    response = client.options(
        "/analyze",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-API-Token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_does_not_allow_unconfigured_origin():
    client = TestClient(
        create_app(
            allow_unauthenticated=True,
            allowed_origins=("https://app.example.com",),
        )
    )

    response = client.options(
        "/analyze",
        headers={
            "Origin": "https://attacker.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-API-Token",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_wildcard_origin_disables_credentials():
    client = TestClient(
        create_app(
            allow_unauthenticated=True,
            allowed_origins=("*",),
        )
    )

    response = client.options(
        "/analyze",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-API-Token",
        },
    )

    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers

"""Streamlit UI E2E 测试配置 — prevents event loop corruption."""

import asyncio

import pytest


@pytest.fixture(scope="session", autouse=True)
def _preserve_event_loop_after_ui_tests():
    """Recreate the event loop after UI tests to prevent cascading failures.

    pytest-playwright's sync API internally uses asyncio and corrupts the
    global event loop state on Windows during `playwright.stop()` teardown.
    Subsequent async tests get RuntimeError: Runner.run() cannot be called.
    """
    yield
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

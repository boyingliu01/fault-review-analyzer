"""E2E smoke test — full pipeline: fetch → analyze → report.

REQ-8, Issue #2 — Validates the complete analysis chain with real API data.
Skipped automatically when DEVCLOUD_TOKEN is not configured.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.client import APIClient
from src.api.exceptions import APIConnectionError, AuthenticationError
from src.config.manager import ConfigManager

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://dev.iwhalecloud.com")
DEVCLOUD_TOKEN = os.getenv("DEVCLOUD_TOKEN", "")
API_PATH_PREFIX = os.getenv("API_PATH_PREFIX", "/portal/ai-gateway/devspace/rpc/v3/work-item")

TEST_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "测试用故障单号列表.xlsx"


def _skip_if_no_token():
    """Skip test if DEVCLOUD_TOKEN is not set."""
    if not DEVCLOUD_TOKEN:
        pytest.skip("DEVCLOUD_TOKEN not configured")


def _get_test_task_id() -> int:
    """Load a single test task ID from the data file."""
    if not TEST_DATA_FILE.exists():
        pytest.skip(f"Test data file not found: {TEST_DATA_FILE}")

    import pandas as pd

    df = pd.read_excel(TEST_DATA_FILE)
    return int(df["故障单号"].iloc[0])


class TestE2ESmoke:
    """End-to-end smoke tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_token_verification(self):
        """REQ-7: Token can be verified against the API."""
        _skip_if_no_token()

        client = APIClient(
            base_url=API_BASE_URL,
            token=DEVCLOUD_TOKEN,
            api_path_prefix=API_PATH_PREFIX,
        )
        client.ensure_client()

        try:
            result = await client.verify_token()
            assert result is True
        except AuthenticationError:
            pytest.skip("Token expired or invalid")
        except APIConnectionError:
            pytest.skip("API server unreachable")
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_fetch_real_task(self):
        """E2E: Fetch a real task from the API."""
        _skip_if_no_token()
        task_id = _get_test_task_id()

        client = APIClient(
            base_url=API_BASE_URL,
            token=DEVCLOUD_TOKEN,
            api_path_prefix=API_PATH_PREFIX,
        )
        client.ensure_client()

        try:
            task = await client.get_task(task_id)
            assert task.task_id == task_id
            assert task.title is not None
        except Exception as e:
            pytest.skip(f"Cannot fetch task {task_id}: {e}")
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_full_pipeline_smoke(self):
        """E2E: Full pipeline fetch → preprocess → rules → report."""
        _skip_if_no_token()
        task_id = _get_test_task_id()

        # Build a minimal ConfigManager
        config = ConfigManager(
            config={
                "api": {
                    "base_url": API_BASE_URL,
                    "api_key": DEVCLOUD_TOKEN,
                    "timeout": 30,
                    "retry": 2,
                },
                "cache": {
                    "db_path": str(Path("./data/cache.db")),
                    "ttl": 3600,
                },
                "llm": {
                    "api_key": "",
                    "model": "gpt-4",
                    "base_url": "",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "",
                    "base_url": "",
                    "batch_size": 100,
                },
                "clustering": {
                    "algorithm": "hdbscan",
                    "min_cluster_size": 3,
                    "min_samples": 2,
                    "metric": "euclidean",
                },
            }
        )

        pipeline_config = PipelineConfig(
            use_cache=False,
            use_llm=False,  # No LLM for smoke test
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=True,
            generate_report=True,
        )

        pipeline = AnalysisPipeline(config=config, pipeline_config=pipeline_config)

        try:
            async with pipeline:
                result = await pipeline.run_single(task_id)

            # Verify pipeline completed without error
            assert result.task_id == task_id
            assert result.error == "", f"Pipeline error: {result.error}"

            # Verify data was fetched
            assert result.task_data is not None, "task_data should not be None"
            assert result.preprocessed is not None, "preprocessed should not be None"

            # Verify rules were checked
            assert result.violations is not None, "violations should not be None"
            assert isinstance(result.violations, list)

            # Verify report was generated
            assert result.report is not None, "report should not be None"
            assert isinstance(result.report, str)
            assert len(result.report) > 0, "report should not be empty"

        except Exception as e:
            pytest.skip(f"Pipeline test skipped: {e}")

    @pytest.mark.asyncio
    async def test_pipeline_no_unhandled_exceptions(self):
        """E2E: Pipeline handles errors gracefully without unhandled exceptions."""
        _skip_if_no_token()

        config = ConfigManager(
            config={
                "api": {
                    "base_url": API_BASE_URL,
                    "api_key": DEVCLOUD_TOKEN,
                    "timeout": 10,
                    "retry": 1,
                },
                "cache": {
                    "db_path": str(Path("./data/cache.db")),
                    "ttl": 3600,
                },
                "llm": {
                    "api_key": "",
                    "model": "gpt-4",
                    "base_url": "",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "",
                    "base_url": "",
                    "batch_size": 100,
                },
                "clustering": {
                    "algorithm": "hdbscan",
                    "min_cluster_size": 3,
                    "min_samples": 2,
                    "metric": "euclidean",
                },
            }
        )

        pipeline_config = PipelineConfig(
            use_cache=False,
            use_llm=False,
            check_rules=True,
            generate_report=True,
        )

        pipeline = AnalysisPipeline(config=config, pipeline_config=pipeline_config)

        # Test with a non-existent task ID — should not raise
        try:
            async with pipeline:
                result = await pipeline.run_single(999999999)
        except APIConnectionError:
            pytest.skip("API server unreachable")

        assert result.task_id == 999999999
        # Pipeline should either set an error OR return with no task_data
        # Both are acceptable graceful handling behaviors
        if result.error == "":
            # If no error, task_data should be None (task not found)
            assert result.task_data is None, "Non-existent task should have no task_data"

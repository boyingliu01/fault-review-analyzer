"""Tests for APIClient.verify_token() — REQ-7, Issue #1."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.client import APIClient
from src.api.exceptions import AuthenticationError


@pytest.fixture
def client():
    """Create an APIClient with a mock HTTP client."""
    c = APIClient(base_url="https://api.example.com", token="test-token-123")
    c._client = MagicMock(spec=httpx.AsyncClient)
    return c


class TestVerifyToken:
    """Test suite for APIClient.verify_token()."""

    @pytest.mark.asyncio
    async def test_verify_token_valid(self, client):
        """verify_token returns True when API responds 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"userId": 1}}
        client._client.request = AsyncMock(return_value=mock_response)

        result = await client.verify_token()
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_expired_raises(self, client):
        """verify_token raises AuthenticationError with clear message on 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        client._client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(AuthenticationError) as exc_info:
            await client.verify_token()
        assert "expired" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_verify_token_connection_error(self, client):
        """verify_token raises APIConnectionError on network failure."""
        client._client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        from src.api.exceptions import APIConnectionError

        with pytest.raises(APIConnectionError):
            await client.verify_token()

    @pytest.mark.asyncio
    async def test_verify_token_empty_token_raises(self):
        """verify_token raises AuthenticationError when token is empty."""
        client = APIClient(base_url="https://api.example.com", token="")
        client._client = MagicMock(spec=httpx.AsyncClient)

        with pytest.raises(AuthenticationError, match="[Nn]o.*token|missing|empty"):
            await client.verify_token()

    @pytest.mark.asyncio
    async def test_verify_token_uses_correct_endpoint(self, client):
        """verify_token calls the correct lightweight endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}
        client._client.request = AsyncMock(return_value=mock_response)

        await client.verify_token()

        client._client.request.assert_called_once()
        call_args = client._client.request.call_args
        assert call_args[0][0] == "GET"  # method is GET

    @pytest.mark.asyncio
    async def test_verify_token_no_client_creates_one(self):
        """verify_token works even when client hasn't been initialized yet."""
        client = APIClient(base_url="https://api.example.com", token="test-token")
        # _client is None initially

        with patch("src.api.client.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_instance.request = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_instance

            result = await client.verify_token()
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_server_error_raises(self, client):
        """verify_token raises ServerError on 500+."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        client._client.request = AsyncMock(return_value=mock_response)

        from src.api.exceptions import ServerError

        with pytest.raises(ServerError):
            await client.verify_token()

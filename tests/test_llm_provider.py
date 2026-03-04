from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyzer.llm_provider import OpenAILLMProvider, create_llm_provider


class TestOpenAILLMProvider:
    def test_init(self):
        provider = OpenAILLMProvider(
            api_key="test-key",
            model="gpt-4",
            temperature=0.7,
            max_tokens=4096,
        )

        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4"
        assert provider.temperature == 0.7
        assert provider.max_tokens == 4096

    def test_init_with_base_url(self):
        provider = OpenAILLMProvider(
            api_key="test-key",
            base_url="https://custom.api.com/v1",
        )

        assert provider.base_url == "https://custom.api.com/v1"

    def test_init_default_base_url(self):
        provider = OpenAILLMProvider(api_key="test-key")

        assert provider.base_url == "https://api.openai.com/v1"

    @pytest.mark.asyncio
    async def test_generate(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAILLMProvider(api_key="test-key")
            result = await provider.generate("System prompt", "User prompt")

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_generate_empty_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAILLMProvider(api_key="test-key")
            result = await provider.generate("System prompt", "User prompt")

            assert result == ""


class TestCreateLLMProvider:
    def test_create_provider_with_api_key(self):
        config = MagicMock()
        config.api_key = "test-key"
        config.model = "gpt-4"
        config.base_url = ""
        config.temperature = 0.7
        config.max_tokens = 4096

        provider = create_llm_provider(config)

        assert provider is not None
        assert provider.api_key == "test-key"

    def test_create_provider_without_api_key(self):
        config = MagicMock()
        config.api_key = ""
        config.model = "gpt-4"
        config.base_url = ""
        config.temperature = 0.7
        config.max_tokens = 4096

        provider = create_llm_provider(config)

        assert provider is None

from typing import Any


class OpenAILLMProvider:
    """OpenAI LLM provider implementation."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the async HTTP client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("openai package is required for LLM features. Install with: pip install openai") from None
        return self._client

    async def generate(self, system: str, user: str) -> str:
        """Generate text using OpenAI API."""
        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return response.choices[0].message.content or ""


def create_llm_provider(config: Any) -> OpenAILLMProvider | None:
    """Create an LLM provider based on configuration."""
    if not config.api_key:
        return None

    return OpenAILLMProvider(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

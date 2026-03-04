from dataclasses import dataclass
from typing import Protocol


class LLMProvider(Protocol):
    """LLM provider protocol for text generation."""

    async def generate(self, system: str, user: str) -> str:
        """Generate text from system and user prompts."""
        ...


@dataclass
class Label:
    """Represents a fault category label."""

    name: str
    confidence: float
    category: str
    description: str = ""


@dataclass
class LabelGenerationResult:
    """Result of label generation for a task cluster."""

    cluster_id: int
    labels: list[Label]
    summary: str
    reasoning: str

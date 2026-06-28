"""Embedding provider abstraction.

v0.1.0 ships with an OpenAI-compatible embedder. Swap implementations by
changing the `embedder` module-level instance at startup.
"""

from typing import TYPE_CHECKING, Protocol

from app.config import settings

if TYPE_CHECKING:
    from openai import OpenAI


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class OpenAIEmbedder:
    def __init__(self) -> None:
        self._dimension = settings.llm.embedding_dimension
        self._model = settings.llm.embedding_model
        self._client: OpenAI | None = None  # Lazy init

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url or None,
            )

        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [d.embedding for d in response.data]


class AnthropicEmbedder:
    """Placeholder for Anthropic embedding support."""

    def __init__(self) -> None:
        raise NotImplementedError("Anthropic embedder is not yet implemented")

    @property
    def dimension(self) -> int:
        return 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Anthropic embedder is not yet implemented")


def _create_embedder() -> Embedder:
    provider = settings.llm.provider
    if provider == "openai":
        return OpenAIEmbedder()
    elif provider == "anthropic":
        raise NotImplementedError("Anthropic embedding not yet supported")
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


embedder: Embedder = _create_embedder()

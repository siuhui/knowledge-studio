"""Embedding provider abstraction.

Uses an OpenAI-compatible embedding API (DashScope text-embedding-v4 by default).
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
        self._dimension = settings.embedding.dimension
        self._model = settings.embedding.model
        self._client: OpenAI | None = None  # Lazy init

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.embedding.api_key.get_secret_value(),
                base_url=settings.embedding.base_url or None,
            )

        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [d.embedding for d in response.data]


embedder: Embedder = OpenAIEmbedder()

"""Embedding provider abstraction.

Uses an OpenAI-compatible embedding API (DashScope text-embedding-v4 by default).
Embedding calls are auto-traced by Langfuse via ``langfuse.openai.OpenAI``.
"""

from typing import Any, Protocol

from app.config import settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class OpenAIEmbedder:
    """OpenAI-compatible embedding provider with Langfuse auto-tracing.

    Uses ``langfuse.openai.OpenAI`` so every embeddings.create call is
    auto-traced with model name and token usage — no manual span needed.
    """

    def __init__(self) -> None:
        self._dimension = settings.embedding.dimension
        self._model = settings.embedding.model
        self._client: Any = None  # langfuse.openai.OpenAI (lazy)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_client(self) -> Any:
        """Lazy-init the OpenAI client — uses Langfuse tracing when available."""
        if self._client is None:
            try:
                from langfuse.openai import OpenAI  # type: ignore[attr-defined]
            except ImportError:
                from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.embedding.api_key.get_secret_value(),
                base_url=settings.embedding.base_url or None,
            )
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        response = client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [d.embedding for d in response.data]


embedder: Embedder = OpenAIEmbedder()

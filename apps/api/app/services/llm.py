"""LLM provider abstraction.

v0.1.0 supports OpenAI and Anthropic chat APIs.
"""

from typing import TYPE_CHECKING, Protocol

import structlog

from app.config import settings

if TYPE_CHECKING:
    from anthropic import Anthropic
    from openai import OpenAI

logger = structlog.get_logger(__name__)


class LLMProvider(Protocol):
    def answer(self, *, query: str, context: str) -> str: ...


class OpenAIProvider:
    def __init__(self) -> None:
        self._model = settings.llm.chat_model
        self._client: OpenAI | None = None  # Lazy init

    def answer(self, *, query: str, context: str) -> str:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url or None,
            )

        system_prompt = (
            "You are a helpful assistant that answers questions based solely on the provided context. "
            "If the context doesn't contain enough information, say so. "
            "Always cite the source document when using information from the context."
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or ""


class AnthropicProvider:
    def __init__(self) -> None:
        self._model = settings.llm.chat_model
        self._client: Anthropic | None = None  # Lazy init

    def answer(self, *, query: str, context: str) -> str:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(
                api_key=settings.llm.api_key.get_secret_value(),
            )

        system_prompt = (
            "You are a helpful assistant that answers questions based solely on the provided context. "
            "If the context doesn't contain enough information, say so. "
            "Always cite the source document when using information from the context."
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
        )
        return str(response.content[0].text)  # type: ignore[union-attr]


def _create_llm_provider() -> LLMProvider:
    provider = settings.llm.provider
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


llm_provider: LLMProvider = _create_llm_provider()

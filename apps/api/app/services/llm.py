"""LLM provider abstraction.

v0.1.0 supports OpenAI and Anthropic chat APIs (sync + async streaming).
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Protocol

import structlog

from app.config import settings

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from openai import AsyncOpenAI, OpenAI

logger = structlog.get_logger(__name__)


class LLMProvider(Protocol):
    def generate(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str: ...

    def generate_stream(self, *, system_prompt: str, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        """Return an async generator that yields text tokens.

        Providers that don't support streaming raise NotImplementedError.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support streaming")


class OpenAIProvider:
    def __init__(self) -> None:
        self._model = settings.llm.chat_model
        self._client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

    def generate(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url or None,
            )

        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,  # type: ignore[arg-type]
            temperature=0.3,
        )
        return response.choices[0].message.content or ""

    async def generate_stream(self, *, system_prompt: str, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream tokens from OpenAI chat completion."""
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url or None,
            )

        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        stream = await self._async_client.chat.completions.create(
            model=self._model,
            messages=full_messages,  # type: ignore[arg-type]
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:  # type: ignore[union-attr]
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class AnthropicProvider:
    def __init__(self) -> None:
        self._model = settings.llm.chat_model
        self._client: Anthropic | None = None
        self._async_client: AsyncAnthropic | None = None

    def generate(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(
                api_key=settings.llm.api_key.get_secret_value(),
            )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
        )
        return str(response.content[0].text)  # type: ignore[union-attr]

    async def generate_stream(self, *, system_prompt: str, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        """Stream tokens from Anthropic Messages API."""
        if self._async_client is None:
            from anthropic import AsyncAnthropic

            self._async_client = AsyncAnthropic(
                api_key=settings.llm.api_key.get_secret_value(),
            )

        async with self._async_client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
        ) as s:
            async for text in s.text_stream:
                yield text


def _create_llm_provider() -> LLMProvider:
    provider = settings.llm.provider
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


llm_provider: LLMProvider = _create_llm_provider()


def get_async_provider() -> LLMProvider:
    """Return a streaming-capable provider instance.

    Reuses the module-level singleton — both OpenAIProvider and
    AnthropicProvider implement generate_stream alongside generate.
    """
    return llm_provider

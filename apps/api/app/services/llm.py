"""LLM provider abstraction.

v0.1.0 supports OpenAI and Anthropic chat APIs (sync + async streaming,
plus tool/function calling for agent mode).
"""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

import structlog
from pydantic import BaseModel

from app.config import settings

if TYPE_CHECKING:
    from anthropic import Anthropic, AsyncAnthropic
    from openai import AsyncOpenAI, OpenAI

logger = structlog.get_logger(__name__)


# ── ToolCallDecision ─────────────────────────────────────────────────────────


class ToolCallDecision(NamedTuple):
    """Normalized LLM tool-call decision — hides provider differences.

    thought is for debugging and frontend display only. The AgentRunner
    loop branches on is_final, not thought.
    """

    is_final: bool  # True = final answer, False = must execute tool
    thought: str | None = None  # Agent reasoning (debug/frontend, may be empty)
    tool_name: str | None = None  # is_final=False: name of tool to call
    tool_args: dict[str, Any] | None = None  # is_final=False: tool parameters
    content: str | None = None  # is_final=True: final answer text
    input_tokens: int = 0  # Prompt tokens consumed (provider-reported, 0 if unavailable)
    output_tokens: int = 0  # Completion tokens consumed (provider-reported, 0 if unavailable)


# ── Minimal tool spec for LLM providers ──────────────────────────────────────


@dataclass
class ToolSpec:
    """Minimal tool description consumed by LLM providers.

    Providers only need name/description/parameters to build function-calling
    schemas — they never execute tools. This avoids circular imports with
    the full Tool protocol in services/agent/.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


# ── LLMProvider Protocol ─────────────────────────────────────────────────────


class LLMProvider(Protocol):
    def generate(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str: ...

    def generate_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        output_schema: type[BaseModel] | None = None,
    ) -> ToolCallDecision:
        """Let the LLM choose a tool to call or produce a final answer.

        Each provider maps ToolSpec → its native tool/function format.
        Returns a normalized ToolCallDecision so AgentRunner never sees
        provider-specific types.

        Design decision: generate() and generate_with_tools() are separate
        methods, not a merged generate(…, tools=None, …). The call sites
        are different (simple Q&A vs agent loop) and the parameter sets
        don't overlap cleanly.
        """
        ...

    def generate_stream(self, *, system_prompt: str, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        """Return an async generator that yields text tokens.

        Providers that don't support streaming raise NotImplementedError.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support streaming")


# ── Helpers: ToolSpec → provider-native schemas ──────────────────────────────


def _to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Convert ToolSpec list to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


# ── OpenAI Provider ──────────────────────────────────────────────────────────


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

    def generate_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        output_schema: type[BaseModel] | None = None,
    ) -> ToolCallDecision:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm.api_key.get_secret_value(),
                base_url=settings.llm.base_url or None,
            )

        full_messages: list[dict[str, Any]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": full_messages,
            "temperature": 0.3,
            "tools": _to_openai_tools(tools),
            "tool_choice": "auto",
        }

        # Structured output via response_format (gpt-4o+ compatible)
        if output_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "schema": output_schema.model_json_schema(),
                },
            }

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        # Extract token usage from response
        usage_input = 0
        usage_output = 0
        if response.usage:
            usage_input = response.usage.prompt_tokens or 0
            usage_output = response.usage.completion_tokens or 0

        # Extract reasoning if available
        thought: str | None = None
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            thought = msg.reasoning_content

        # Check for tool calls
        if msg.tool_calls:
            if len(msg.tool_calls) > 1:
                logger.warning(
                    "LLM returned multiple tool calls, only first will be used",
                    count=len(msg.tool_calls),
                    tools=[tc.function.name for tc in msg.tool_calls],
                )
            tc = msg.tool_calls[0]
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_args = {"raw": tc.function.arguments}
            return ToolCallDecision(
                is_final=False,
                thought=thought,
                tool_name=tool_name,
                tool_args=tool_args,
                content=None,
                input_tokens=usage_input,
                output_tokens=usage_output,
            )

        # No tool calls → final answer
        return ToolCallDecision(
            is_final=True,
            thought=thought,
            tool_name=None,
            tool_args=None,
            content=msg.content or "",
            input_tokens=usage_input,
            output_tokens=usage_output,
        )

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


# ── Anthropic Provider ───────────────────────────────────────────────────────


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

    def generate_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        output_schema: type[BaseModel] | None = None,
    ) -> ToolCallDecision:
        raise NotImplementedError(
            "Anthropic tool calling is not yet supported for agent mode. "
            "Use an OpenAI-compatible provider (set KB_LLM__PROVIDER=openai)."
        )

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


# ── Factory ──────────────────────────────────────────────────────────────────


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

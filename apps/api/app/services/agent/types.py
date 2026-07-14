"""Agent runtime core types.

AgentConfig and AgentRunner are separated: Config is serializable pure data,
Runner is a stateless executor. Same Runner + different Config = different Agent.
"""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ── ToolContext ──────────────────────────────────────────────────────────────


@dataclass
class ToolContext:
    """Shared context passed to every tool execution.

    Carries db via context rather than coupling Tool interface to the database.
    v0.1.0 only carries db and kb_id; extensible as needed.
    """

    db: "Session"
    kb_id: str
    user_id: str | None = None


# ── Tool Protocol ────────────────────────────────────────────────────────────


class Tool(Protocol):
    """Tool protocol. Any object implementing this can be used as an agent tool."""

    name: str
    description: str  # Natural language description, injected into system prompt
    parameters: dict[str, Any]  # JSON Schema, injected into function calling

    def execute(self, ctx: ToolContext, **kwargs: object) -> "ToolResult": ...


# ── Artifact ─────────────────────────────────────────────────────────────────


@dataclass
class Artifact:
    """A single piece of data produced by a tool.

    JSON-serializability is validated at construction time so downstream
    consumers (SSE, API response) never encounter unserializable data.
    """

    data: dict[str, object]  # JSON-serializable dict
    doc_id: str | None = None  # Originating document ID, used for citation

    def __post_init__(self) -> None:
        try:
            json.dumps(self.data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Artifact data must be JSON-serializable: {e}") from e

    def to_json(self) -> str:
        return json.dumps(self.data)


# ── ToolResult ───────────────────────────────────────────────────────────────


@dataclass
class ToolResult:
    """Result of a tool execution.

    summary:
        Short natural-language summary for the LLM (200-500 chars recommended).
        Avoids bloating the context window with full document text.
    artifacts:
        Complete structured data for the caller to collect. Each Artifact is
        validated as JSON-serializable at construction time.
    metadata:
        Runtime metrics for tracing/monitoring (latency_ms, document_ids, etc.).
    """

    summary: str
    artifacts: list[Artifact]
    artifact_count: int
    metadata: dict[str, object] = field(default_factory=dict)


# ── AgentStep ────────────────────────────────────────────────────────────────


@dataclass
class AgentStep:
    """Single step record — supports SSE event streaming and debug replay.

    thought is for debugging and frontend display only. The Runner loop
    does NOT depend on this field for control flow. Set to None when
    the provider cannot supply reasoning.
    """

    thought: str | None
    tool_name: str | None
    tool_args: dict[str, Any] | None
    tool_result: ToolResult | None
    is_final: bool
    new_info_count: int


# ── AgentUsage ───────────────────────────────────────────────────────────────


@dataclass
class AgentUsage:
    """LLM token consumption summary aggregated across all rounds."""

    input_tokens: int
    output_tokens: int
    total_tool_calls: int
    latency_ms: float


# ── AgentConfig ──────────────────────────────────────────────────────────────


@dataclass
class AgentConfig:
    """Complete agent configuration.

    Same AgentRunner + different AgentConfig = different agent behavior.
    Configs are serializable pure data — cacheable at process level.
    """

    tools: list[Tool]
    system_prompt: str
    max_rounds: int = 5
    early_stop_patience: int = 2  # Consecutive rounds with 0 new artifacts → stop
    output_schema: type[BaseModel] | None = None  # Optional structured output schema

    def __post_init__(self) -> None:
        """Build tool registry: O(1) lookup, duplicate-name guard."""
        self._tool_registry: dict[str, Tool] = {t.name: t for t in self.tools}
        if len(self._tool_registry) != len(self.tools):
            raise ValueError("Duplicate tool names in AgentConfig")

    def has_tool(self, name: str) -> bool:
        """Check whether a tool with the given name is registered."""
        return name in self._tool_registry

    def get_tool(self, name: str) -> Tool:
        return self._tool_registry[name]


# ── AgentResult ──────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    """Final product of an agent run."""

    steps: list[AgentStep]  # Full reasoning trace
    collected_artifacts: list[Artifact]  # All tool artifacts aggregated
    final_answer: str | None  # Natural-language output when is_final
    total_rounds: int
    total_tool_calls: int
    usage: AgentUsage | None  # Token consumption

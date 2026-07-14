"""Agent runtime — stateless ReAct loop with configurable tools.

Public API:
  AgentRunner  — stateless ReAct execution engine
  AgentConfig  — serializable agent configuration
  Tool         — tool protocol
  ToolContext  — shared execution context (db, kb_id)
  ToolResult   — tool execution result (summary + artifacts)
  Artifact     — single piece of tool-produced data
  AgentResult  — final product of an agent run
  AgentStep    — single step record (for streaming/debugging)
  AgentUsage   — token consumption summary

Pre-built configs (from configs.py):
  SEARCH_AGENT_CONFIG   — search agent (max 4 rounds)
  GATHER_AGENT_CONFIG   — gather agent (max 8 rounds)

Built-in tools (from tools.py):
  hybrid_search   — FTS + vector + RRF on Chunk
  read_document   — read Document.full_text by offset
  list_documents  — list all documents in KB
"""

from app.services.agent.configs import GATHER_AGENT_CONFIG, SEARCH_AGENT_CONFIG
from app.services.agent.runner import AgentRunner
from app.services.agent.tools import hybrid_search, list_documents, read_document
from app.services.agent.types import (
    AgentConfig,
    AgentResult,
    AgentStep,
    AgentUsage,
    Artifact,
    ToolContext,
    ToolResult,
)

__all__ = [
    # Runner
    "AgentRunner",
    # Types
    "AgentConfig",
    "AgentResult",
    "AgentStep",
    "AgentUsage",
    "Artifact",
    "ToolContext",
    "ToolResult",
    # Configs
    "GATHER_AGENT_CONFIG",
    "SEARCH_AGENT_CONFIG",
    # Tools
    "hybrid_search",
    "list_documents",
    "read_document",
]

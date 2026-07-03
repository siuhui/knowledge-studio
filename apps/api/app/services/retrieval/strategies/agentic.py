"""Agentic search strategy — multi-round LLM-driven keyword retrieval.

Uses AgentRunner + SEARCH_AGENT_CONFIG to perform iterative search
(think → search → read → cross-check → answer) on Document.full_text.
Zero embedding cost — relies on PostgreSQL FTS only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy.orm import Session

from app.schemas.retrieval.citation import Citation
from app.schemas.retrieval.response import RetrievalChunk, RetrievalQueryResponse
from app.services.agent.types import AgentResult, AgentStep, Artifact, ToolContext
from app.services.retrieval.strategies import register

if TYPE_CHECKING:
    from app.services.agent.runner import AgentRunner

logger = structlog.get_logger(__name__)


# ── Progress event builder ─────────────────────────────────────────────────────
#
# Each tool invocation is mapped to a structured ``agent_progress`` event
# with a ``status`` enum and key metrics.  The frontend owns all display
# strings — the backend never hardcodes user-facing text.


def _tool_progress(
    tool_name: str,
    tool_args: dict[str, object],
    tool_result: object,  # ToolResult
) -> dict[str, object]:
    """Build a structured agent_progress event from a tool invocation.

    Status values (frontend picks the display label):
    - ``listing``   — enumerating available documents
    - ``searching`` — keyword search in progress / completed
    - ``reading``   — reading a specific document
    - ``analyzing`` — final synthesis before LLM streaming
    - ``error``     — tool or agent loop error
    """
    count: int = getattr(tool_result, "artifact_count", 0)
    artifacts: list[Artifact] = getattr(tool_result, "artifacts", []) or []

    if tool_name == "list_documents":
        return {
            "type": "agent_progress",
            "status": "listing",
            "document_count": count,
        }

    if tool_name == "search_keywords":
        query = str(tool_args.get("query", ""))
        return {
            "type": "agent_progress",
            "status": "searching",
            "query": query,
            "hits": count,
        }

    if tool_name == "read_document":
        title = str(artifacts[0].data.get("title", "")) if artifacts else ""
        return {
            "type": "agent_progress",
            "status": "reading",
            "document_title": title,
            "found": count > 0,
        }

    # Unknown tool — generic event
    return {"type": "agent_progress", "status": "searching"}


def _steps_to_sse_events(steps: list[AgentStep]) -> list[dict[str, object]]:
    """Convert AgentStep list to structured agent_progress SSE events.

    Only tool-result pairs are emitted (one event per completed tool call).
    Thought-only steps are skipped — they add no information the frontend
    can use beyond what the tool-result pair already conveys.
    """
    events: list[dict[str, object]] = []

    for step in steps:
        # ── Final answer step ──
        if step.is_final:
            events.append({"type": "agent_progress", "status": "analyzing"})
            break

        # ── Thought-only step (before tool call) — skip ──
        # Also catches error steps (LLM exception with all fields None)
        # and thought steps from non-reasoning models (thought=None).
        # Real errors are surfaced via the SSE stream's error event, not here.
        if step.tool_name is None:
            continue

        # ── Tool call + result pair ──
        if step.tool_name is not None and step.tool_result is not None:
            events.append(_tool_progress(step.tool_name, step.tool_args or {}, step.tool_result))

    return events


# ── Response builder ───────────────────────────────────────────────────────────


def _artifacts_to_response(
    *,
    query: str,
    artifacts: list[Artifact],
    agent_steps: list[dict[str, object]] | None = None,
) -> RetrievalQueryResponse:
    """Convert collected agent artifacts into a RetrievalQueryResponse.

    Each artifact carries document-level data (no Chunk).  We build
    synthetic chunk_ids and document-level citations so the downstream
    ChatService._build_context / _build_citations work unchanged.
    """
    results: list[RetrievalChunk] = []
    seen_ids: set[str] = set()

    for i, a in enumerate(artifacts):
        data = a.data
        doc_id = str(data.get("doc_id", ""))
        title = str(data.get("title", "Unknown"))

        # Prefer full content from read_document; fall back to snippet
        content = str(data.get("content", data.get("snippet", "")))
        if not content:
            continue

        # Deduplicate by document — first result wins (highest rank)
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)

        # Score: rank from FTS (lower = better), or 1.0 for read_document
        rank_val = data.get("rank")
        if isinstance(rank_val, (int, float)):
            score = float(rank_val)
        else:
            score = 1.0

        # Build document-level citation (no chunk_index since we search full_text)
        citation = Citation(
            document_id=doc_id,
            document_title=title,
            chunk_index=0,
            content_snippet=content[:200],
        )

        # Synthetic chunk_id for compatibility with RetrievalChunk schema
        chunk_id = f"{doc_id}:a{i}"

        results.append(
            RetrievalChunk(
                chunk_id=chunk_id,
                content=content,
                score=score,
                document_title=title,
                citation=citation,
            )
        )

    if not results and artifacts:
        # We had artifacts but none with usable content — include at most
        # one per document as a citation-only result
        for a in artifacts:
            data = a.data
            doc_id = str(data.get("doc_id", ""))
            title = str(data.get("title", "Unknown"))
            snippet = str(data.get("snippet", data.get("content", "")))
            if not doc_id or doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            results.append(
                RetrievalChunk(
                    chunk_id=doc_id,
                    content=snippet[:500],
                    score=0.0,
                    document_title=title,
                    citation=Citation(
                        document_id=doc_id,
                        document_title=title,
                        chunk_index=0,
                        content_snippet=snippet[:200],
                    ),
                )
            )
            if len(results) >= 5:
                break

    return RetrievalQueryResponse(
        query=query,
        results=results,
        agent_steps=agent_steps,
    )


# ── Strategy ───────────────────────────────────────────────────────────────────


@register("agentic")
class AgenticSearchStrategy:
    """Multi-round LLM-driven keyword search — zero embedding cost.

    Internally runs AgentRunner(SEARCH_AGENT_CONFIG) which iteratively
    calls search_keywords → read_document → cross-check until it can
    answer the question or hits the early-stop / max-round limit.
    """

    def __init__(self) -> None:
        self._agent: AgentRunner | None = None  # Lazy init

    def _get_agent(self) -> AgentRunner:
        """Lazy-init the AgentRunner to avoid import-time LLM client creation."""
        if self._agent is None:
            from app.services.agent import SEARCH_AGENT_CONFIG, AgentRunner
            from app.services.llm import llm_provider

            self._agent = AgentRunner(llm_provider, SEARCH_AGENT_CONFIG)
        return self._agent

    def search(
        self,
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
        document_ids: list[str] | None = None,
    ) -> RetrievalQueryResponse:
        agent = self._get_agent()

        # Build task description — include document_ids constraint when specified
        task_parts = [f"Answer this question using the knowledge base:\n{query}"]
        if document_ids:
            task_parts.append(f"\nOnly search within these document IDs: {', '.join(document_ids)}")
        task = "\n".join(task_parts)

        ctx = ToolContext(db=db, kb_id=knowledge_base_id)
        result: AgentResult = agent.run(task, ctx)

        # Build SSE-compatible event list from agent steps
        agent_steps = _steps_to_sse_events(result.steps)

        logger.info(
            "agentic retrieval completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            rounds=result.total_rounds,
            tool_calls=result.total_tool_calls,
            artifacts=len(result.collected_artifacts),
            final_answer=bool(result.final_answer),
        )

        return _artifacts_to_response(
            query=query,
            artifacts=result.collected_artifacts,
            agent_steps=agent_steps,
        )

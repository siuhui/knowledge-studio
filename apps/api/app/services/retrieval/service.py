"""Retrieval service — direct (hybrid) and agentic retrieval modes.

``search()`` dispatches by mode ("direct" | "agentic").  Direct mode runs a
single pass through ``hybrid_retrieve()`` + ``merge_results()``.  Agentic mode
runs a multi-round AgentRunner loop with ``hybrid_search`` + ``read_document``
tools.  Both return a uniform ``RetrievalQueryResponse``.
"""

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.core.response_codes import ResponseCode
from app.core.telemetry import observe, update_current_span
from app.models.document import Document
from app.schemas.retrieval.response import RetrievalChunk, RetrievalQueryResponse
from app.services.embedding import embedder
from app.services.retrieval.citation_builder import build_citations
from app.services.retrieval.reranker import rerank
from app.services.retrieval.retriever import hybrid_retrieve, merge_results

logger = structlog.get_logger(__name__)


class RetrievalService:
    """Unified retrieval entry point.

    Two modes, one uniform response:
    - ``direct``  — single-pass hybrid retrieval (FTS + vector + RRF)
    - ``agentic`` — multi-round agent loop (hybrid_search + read_document + list_documents)
    """

    DEFAULT_MODE = "direct"

    # ── Public API ──────────────────────────────────────────────────────────

    @staticmethod
    @observe(name="search.retrieve", as_type="retriever", capture_input=False, capture_output=False)
    def search(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
        document_ids: list[str] | None = None,
        mode: str | None = None,
        lexical_queries: list[str] | None = None,
    ) -> RetrievalQueryResponse:
        mode_name = mode or RetrievalService.DEFAULT_MODE

        update_current_span(
            input={
                "query": query[:200],
                "top_k": top_k,
                "mode": mode_name,
            },
        )

        if mode_name == "direct":
            result = RetrievalService._direct_search(
                db,
                query=query,
                knowledge_base_id=knowledge_base_id,
                top_k=top_k,
                document_ids=document_ids,
                lexical_queries=lexical_queries,
            )
        elif mode_name == "agentic":
            result = RetrievalService._agentic_search(
                db,
                query=query,
                knowledge_base_id=knowledge_base_id,
                top_k=top_k,
                document_ids=document_ids,
            )
        else:
            raise ValidationError(
                code=ResponseCode.SEARCH_STRATEGY_UNKNOWN,
                message=(f"Unknown search mode: '{mode_name}'. Available: ['direct', 'agentic']"),
            )

        update_current_span(
            output={
                "results_count": len(result.results),
                "top_score": result.results[0].score if result.results else None,
                "has_agent_steps": result.agent_steps is not None,
            },
        )

        return result

    # ── Direct mode ─────────────────────────────────────────────────────────

    @staticmethod
    def _direct_search(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int,
        document_ids: list[str] | None,
        lexical_queries: list[str] | None,
    ) -> RetrievalQueryResponse:
        """Single-pass hybrid retrieval — FTS + vector + RRF."""
        queries = lexical_queries or [query]

        raw = hybrid_retrieve(
            db,
            semantic_query=query,
            lexical_queries=queries,
            knowledge_base_id=knowledge_base_id,
            embedder=embedder,
            top_k=top_k,
            document_ids=document_ids,
        )
        merged = merge_results(raw, top_k=top_k)

        if merged.both_failed or not merged.chunks:
            return RetrievalQueryResponse(query=query, results=[])

        chunk_scores = rerank(merged.chunks)

        # Batch-fetch documents for titles
        doc_ids_set = {c.doc_id for c, _ in chunk_scores}
        docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids_set)).all()} if doc_ids_set else {}

        results: list[RetrievalChunk] = []
        for chunk, score in chunk_scores:
            doc = docs.get(chunk.doc_id)
            if doc is None:
                continue
            results.append(
                RetrievalChunk(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    score=score,
                    document_title=doc.title,
                    section_path=chunk.section_path if isinstance(chunk.section_path, list) else [],
                    citation=build_citations([(chunk, doc, score)])[0],
                )
            )

        logger.info(
            "direct retrieval completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            result_count=len(results),
            fts_error=bool(merged.fts_error),
            vector_error=bool(merged.vector_error),
        )

        return RetrievalQueryResponse(query=query, results=results)

    # ── Agentic mode ────────────────────────────────────────────────────────

    @staticmethod
    def _agentic_search(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int,
        document_ids: list[str] | None,
    ) -> RetrievalQueryResponse:
        """Multi-round agent-driven retrieval with hybrid_search + read_document."""
        from app.schemas.retrieval.citation import Citation
        from app.services.agent import SEARCH_AGENT_CONFIG, AgentRunner
        from app.services.agent.types import ToolContext
        from app.services.llm import llm_provider

        agent = AgentRunner(llm_provider, SEARCH_AGENT_CONFIG)

        task_parts = [f"Answer this question using the knowledge base:\n{query}"]
        if document_ids:
            task_parts.append(f"\nOnly search within these document IDs: {', '.join(document_ids)}")
        task = "\n".join(task_parts)

        ctx = ToolContext(db=db, kb_id=knowledge_base_id)
        result = agent.run(task, ctx)

        # Build agent_progress SSE events from steps
        agent_steps = _build_agent_progress_events(result.steps)

        # Convert artifacts to RetrievalChunk list.
        #
        # Dedup by span (doc_id, start_offset, end_offset), NOT by doc_id.
        # An agent can legitimately surface multiple distinct chunks from the
        # same document across rounds — doc-level dedup would collapse them to
        # one and drop real context.  Span dedup only removes exact repeats
        # (the same chunk re-hit by near-identical queries across rounds).
        results: list[RetrievalChunk] = []
        seen_spans: set[tuple[str, int, int]] = set()

        for i, a in enumerate(result.collected_artifacts):
            data = a.data
            doc_id = str(data.get("doc_id", ""))
            title = str(data.get("title", "Unknown"))

            content = str(data.get("content", data.get("snippet", "")))
            if not content:
                continue

            start_offset, end_offset = _artifact_offsets(data, content)

            span = (doc_id, start_offset, end_offset)
            if span in seen_spans:
                continue
            seen_spans.add(span)

            rank_val = data.get("rank")
            score = float(rank_val) if isinstance(rank_val, (int, float)) else 1.0

            citation = Citation(
                document_id=doc_id,
                document_title=title,
                chunk_index=0,
                content_snippet=content[:200],
                start_offset=start_offset,
                end_offset=end_offset,
            )
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

        if not results and result.collected_artifacts:
            for a in result.collected_artifacts:
                data = a.data
                doc_id = str(data.get("doc_id", ""))
                title = str(data.get("title", "Unknown"))
                snippet = str(data.get("snippet", data.get("content", "")))
                if not doc_id:
                    continue
                start_offset, end_offset = _artifact_offsets(data, snippet[:500])
                span = (doc_id, start_offset, end_offset)
                if span in seen_spans:
                    continue
                seen_spans.add(span)
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
                            start_offset=start_offset,
                            end_offset=end_offset,
                        ),
                    )
                )
                if len(results) >= 5:
                    break

        logger.info(
            "agentic retrieval completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            rounds=result.total_rounds,
            tool_calls=result.total_tool_calls,
            artifacts=len(result.collected_artifacts),
            final_answer=bool(result.final_answer),
        )

        return RetrievalQueryResponse(
            query=query,
            results=results,
            agent_steps=agent_steps,
        )


# ── Artifact offset extraction ─────────────────────────────────────────────────


def _artifact_offsets(data: dict[str, Any], content: str) -> tuple[int, int]:
    """Recover (start_offset, end_offset) from an agent tool artifact.

    Two artifact shapes carry position info:
    - hybrid_search: ``start_offset`` + ``end_offset`` (authoritative, from Chunk)
    - read_document: ``offset`` + ``length`` (end derived as offset + length)

    list_documents artifacts have no position — fall back to (0, len(content)).
    """
    if "start_offset" in data and "end_offset" in data:
        return int(data["start_offset"]), int(data["end_offset"])
    if "offset" in data:
        start = int(data["offset"])
        length = int(data["length"]) if "length" in data else len(content)
        return start, start + length
    return 0, len(content)


# ── Agent progress event builder ──────────────────────────────────────────────


def _build_agent_progress_events(steps: list[Any]) -> list[dict[str, object]]:  # noqa: C901
    """Convert AgentStep list to structured agent_progress SSE events."""
    from app.services.agent.types import Artifact

    events: list[dict[str, object]] = []

    for step in steps:
        if step.is_final:
            events.append({"type": "agent_progress", "status": "analyzing"})
            break

        if step.tool_name is None:
            continue

        if step.tool_name is not None and step.tool_result is not None:
            tool_name = step.tool_name
            tool_args = step.tool_args or {}
            tool_result = step.tool_result
            count: int = getattr(tool_result, "artifact_count", 0)
            artifacts: list[Artifact] = getattr(tool_result, "artifacts", []) or []

            if tool_name == "list_documents":
                events.append(
                    {
                        "type": "agent_progress",
                        "status": "listing",
                        "document_count": count,
                    }
                )
            elif tool_name == "hybrid_search":
                query_str = str(tool_args.get("embedding_query", ""))
                events.append(
                    {
                        "type": "agent_progress",
                        "status": "searching",
                        "query": query_str,
                        "hits": count,
                    }
                )
            elif tool_name == "read_document":
                title = str(artifacts[0].data.get("title", "")) if artifacts else ""
                events.append(
                    {
                        "type": "agent_progress",
                        "status": "reading",
                        "document_title": title,
                        "found": count > 0,
                    }
                )
            else:
                events.append({"type": "agent_progress", "status": "searching"})

    return events

"""Built-in agent tools for knowledge base search.

Tools use the unified ``hybrid_retrieve`` + ``merge_results`` pipeline
from ``services/retrieval/retriever.py`` which searches Chunk via FTS + vector.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from app.models.document import Document
from app.services.agent.types import Artifact, ToolContext, ToolResult

logger = structlog.get_logger(__name__)


def _read_document_impl(
    ctx: ToolContext,
    document_id: str,
    offset: int = 0,
    length: int = 3000,
) -> ToolResult:
    """Read a slice of a document's full_text by character offset."""
    t0 = time.perf_counter()
    doc = ctx.db.get(Document, document_id)

    if doc is None:
        return ToolResult(
            summary=(
                f"Document '{document_id}' not found. "
                "Document IDs are UUIDs (e.g. '550e8400-e29b-41d4-a716-446655440000'). "
                "Use list_documents to get the correct UUID for each document. "
                "Do NOT pass document titles — only UUIDs work."
            ),
            artifacts=[],
            artifact_count=0,
            metadata={"document_id": document_id},
        )

    if doc.knowledge_base_id != ctx.kb_id:
        return ToolResult(
            summary=f"Document {document_id} does not belong to this knowledge base.",
            artifacts=[],
            artifact_count=0,
            metadata={"document_id": document_id},
        )

    full_text = doc.full_text
    total_chars = len(full_text)
    snippet = full_text[offset : offset + length]
    actual_length = len(snippet)

    summary = (
        f"Document: {doc.title}\n"
        f"Position: chars {offset}-{offset + actual_length} of {total_chars}\n"
        f"Content preview:\n{snippet[:300]}"
    )

    artifact = Artifact(
        data={
            "doc_id": document_id,
            "title": doc.title,
            "offset": offset,
            "length": actual_length,
            "total_chars": total_chars,
            "content": snippet,
        },
        doc_id=document_id,
    )

    logger.info(
        "read_document executed",
        document_id=document_id,
        offset=offset,
        length=actual_length,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )

    return ToolResult(
        summary=summary,
        artifacts=[artifact],
        artifact_count=1,
        metadata={
            "document_id": document_id,
            "total_chars": total_chars,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        },
    )


def _list_documents_impl(ctx: ToolContext) -> ToolResult:
    """List all ready documents in the knowledge base."""
    t0 = time.perf_counter()
    docs = (
        ctx.db.query(Document)
        .filter(Document.knowledge_base_id == ctx.kb_id, Document.status == "ready")
        .order_by(Document.title)
        .all()
    )

    if not docs:
        return ToolResult(
            summary="No documents found in this knowledge base.",
            artifacts=[],
            artifact_count=0,
            metadata={"document_count": 0},
        )

    artifacts = [
        Artifact(
            data={
                "doc_id": d.id,
                "title": d.title,
                "format": d.source_format,
                "size_chars": len(d.full_text),
            },
            doc_id=d.id,
        )
        for d in docs
    ]

    lines = [
        f"{i + 1}. UUID={d.id} | title='{d.title}' | format={d.source_format} | size={len(d.full_text)} chars"
        for i, d in enumerate(docs)
    ]
    summary = (
        f"Found {len(docs)} document(s). Use the UUID (not title) with read_document or hybrid_search:\n"
        + "\n".join(lines[:20])
    )
    if len(docs) > 20:
        summary += f"\n... and {len(docs) - 20} more."

    logger.info(
        "list_documents executed",
        kb_id=ctx.kb_id,
        count=len(docs),
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )

    return ToolResult(
        summary=summary,
        artifacts=artifacts,
        artifact_count=len(artifacts),
        metadata={"document_count": len(docs), "latency_ms": round((time.perf_counter() - t0) * 1000, 2)},
    )


# ── Hybrid search tool (Phase 2) ─────────────────────────────────────────────


def _hybrid_search_impl(
    ctx: ToolContext,
    embedding_query: str,
    lexical_queries: list[str] | None = None,
    document_ids: list[str] | None = None,
    top_k: int = 5,
) -> ToolResult:
    """Agent tool: hybrid search (FTS + vector + RRF) on Chunk table.

    Uses the unified ``hybrid_retrieve()`` + ``merge_results()`` pipeline.
    Both paths are fault-tolerant — if one fails the other continues.
    Returns Chunk-level artifacts with ``start_offset`` / ``end_offset``
    so the agent can use them directly with ``read_document``.
    """
    from app.services.embedding import embedder
    from app.services.retrieval.retriever import hybrid_retrieve, merge_results

    t0 = time.perf_counter()
    queries = lexical_queries or [embedding_query]

    raw = hybrid_retrieve(
        ctx.db,
        semantic_query=embedding_query,
        lexical_queries=queries,
        knowledge_base_id=ctx.kb_id,
        embedder=embedder,
        top_k=top_k,
        document_ids=document_ids,
    )
    merged = merge_results(raw, top_k=top_k)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if merged.both_failed:
        return ToolResult(
            summary=(
                "Search is currently unavailable. "
                f"FTS error: {merged.fts_error}. Vector error: {merged.vector_error}. "
                "Tell the user to try again later."
            ),
            artifacts=[],
            artifact_count=0,
            metadata={
                "latency_ms": round(elapsed_ms, 2),
                "fts_error": merged.fts_error,
                "vector_error": merged.vector_error,
            },
        )

    if not merged.chunks:
        return ToolResult(
            summary="No results found. Try different lexical_queries or broader terms.",
            artifacts=[],
            artifact_count=0,
            metadata={"latency_ms": round(elapsed_ms, 2)},
        )

    # Build Chunk-level artifacts with offset info for read_document
    artifacts = []
    for i, (chunk, score) in enumerate(merged.chunks):
        start_offset = getattr(chunk, "start_offset", 0)
        end_offset = getattr(chunk, "end_offset", len(chunk.content))
        artifacts.append(
            Artifact(
                data={
                    "chunk_id": chunk.id,
                    "doc_id": chunk.doc_id,
                    "content": chunk.content,
                    "score": round(score, 4),
                    "rank": i + 1,
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                },
                doc_id=chunk.doc_id,
            )
        )

    # Build compact summary for LLM
    lines = []
    for i, (chunk, score) in enumerate(merged.chunks[:5]):
        lines.append(f"[{i + 1}] doc={chunk.doc_id} score={score:.4f}: {chunk.content[:120]}")
    summary = "\n".join(lines) if lines else "No results found."
    if len(merged.chunks) > 5:
        summary += f"\n... and {len(merged.chunks) - 5} more results."

    logger.info(
        "hybrid_search executed",
        embedding_query=embedding_query[:100],
        lexical_queries=queries,
        kb_id=ctx.kb_id,
        result_count=len(artifacts),
        latency_ms=round(elapsed_ms, 2),
    )

    return ToolResult(
        summary=summary,
        artifacts=artifacts,
        artifact_count=len(artifacts),
        metadata={
            "latency_ms": round(elapsed_ms, 2),
            "result_count": len(artifacts),
            "fts_error": merged.fts_error is not None,
            "vector_error": merged.vector_error is not None,
        },
    )


# ── Tool definitions ─────────────────────────────────────────────────────────


@dataclass
class _ToolDef:
    """Concrete tool definition satisfying the Tool protocol.

    Plain functions stored as instance attributes do not trigger Python's
    descriptor protocol, so ``tool.execute(ctx, **kwargs)`` calls the
    underlying implementation directly — no implicit self argument.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., ToolResult]


hybrid_search = _ToolDef(
    name="hybrid_search",
    description=(
        "Hybrid search (full-text + semantic vector) across all documents in one call. "
        "Takes two kinds of input: embedding_query for semantic (vector) similarity, "
        "lexical_queries for exact word matching via full-text search. "
        "If lexical_queries is omitted, the embedding_query is used for FTS as well. "
        "Returns chunk-level results with start_offset/end_offset for use with read_document."
    ),
    parameters={
        "type": "object",
        "properties": {
            "embedding_query": {
                "type": "string",
                "description": (
                    "A natural language description of what you're looking for in THIS search round. "
                    "For the first search, use the original user question. "
                    "In follow-up rounds when you've narrowed your focus, refine this to match "
                    "your current search intent."
                ),
            },
            "lexical_queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "1-3 focused short query phrases for exact word matching. "
                    "Not isolated keywords — use concise phrases matching the query language. "
                    "EN: 'SQL injection prevention'  ZH: 'SQL注入防护'. "
                    "For Chinese, use meaningful 2-4 character sequences, not single chars. "
                    "Each phrase runs as an independent FTS query; results are merged via RRF. "
                    "Omit to use embedding_query for FTS as well."
                ),
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of document UUIDs to limit the search scope.",
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return (default 5).",
            },
        },
        "required": ["embedding_query"],
    },
    execute=_hybrid_search_impl,
)

read_document = _ToolDef(
    name="read_document",
    description=(
        "Read a specific portion of a document's full text by character offset. "
        "Use hybrid_search or list_documents first to obtain the correct document UUID, "
        "then use this tool to read the full surrounding context. "
        "IMPORTANT: document_id must be a UUID, never a document title. "
        "TIP: when reading context around a chunk found via hybrid_search, "
        "use the chunk's start_offset directly as the offset parameter."
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": (
                    "UUID of the document to read (e.g. '550e8400-e29b-41d4-a716-446655440000'). "
                    "Must be an exact UUID obtained from list_documents or hybrid_search results. "
                    "Do NOT pass a document title, filename, or any other string — only a UUID."
                ),
            },
            "offset": {
                "type": "integer",
                "description": (
                    "Starting character position (0-based). Default 0 for beginning of document. "
                    "When reading around a chunk from hybrid_search, use the chunk's start_offset value directly."
                ),
            },
            "length": {
                "type": "integer",
                "default": 3000,
                "description": "Number of characters to read (default 3000).",
            },
        },
        "required": ["document_id"],
    },
    execute=_read_document_impl,
)

list_documents = _ToolDef(
    name="list_documents",
    description=(
        "List all documents in the knowledge base with their UUID IDs, titles, formats, and sizes. "
        "Always call this first to discover available documents and their UUIDs. "
        "The returned UUIDs are needed for hybrid_search (to scope) and read_document (to read)."
    ),
    parameters={"type": "object", "properties": {}},
    execute=_list_documents_impl,
)

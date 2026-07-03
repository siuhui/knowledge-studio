"""Built-in agent tools for knowledge base search.

All three tools operate on Document.full_text via PostgreSQL — no Chunk,
no embedding dependency. Designed for agentic (keyword-driven) search.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.agent.types import Artifact, ToolContext, ToolResult

logger = structlog.get_logger(__name__)

# ── Summary builder ──────────────────────────────────────────────────────────


def _build_summary(rows: list[dict[str, Any]], max_chars: int = 500) -> str:
    """Build a compact summary from search result rows for the LLM."""
    if not rows:
        return "No results found."
    lines: list[str] = []
    total = 0
    for r in rows:
        line = f"[{r['rank']}] UUID={r['id']} | {r['title']}: {r['snippet'][:120]}"
        if total + len(line) > max_chars:
            lines.append(f"... ({len(rows) - len(lines)} more results)")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


# ── FTS helper ───────────────────────────────────────────────────────────────


# pgvector FTS config used for all text-search operations.
# 'simple' is chosen over 'english' because it does not strip stopwords
# or apply English-specific stemming — it only lowercases and splits on
# whitespace/punctuation, making it usable for mixed-language corpora
# (e.g. Chinese, Japanese, Korean alongside English).
_FTS_CONFIG = "simple"


def _execute_fts(
    db: Session,
    kb_id: str,
    query: str,
    document_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Execute PostgreSQL FTS on Document.full_text with ts_headline snippets.

    Uses plainto_tsquery for user-friendly search — no tsquery syntax required.
    """
    ts_vector = func.to_tsvector(_FTS_CONFIG, Document.full_text)
    ts_query = func.plainto_tsquery(_FTS_CONFIG, query)

    q = (
        db.query(
            Document.id.label("id"),
            Document.title.label("title"),
            func.ts_headline(_FTS_CONFIG, Document.full_text, ts_query, "MaxWords=40, MinWords=15, ShortWord=3").label(
                "snippet"
            ),
            func.ts_rank(ts_vector, ts_query).label("rank"),
        )
        .filter(Document.knowledge_base_id == kb_id)
        .filter(Document.status == "ready")
        .filter(ts_vector.match(query, postgresql_regconfig=_FTS_CONFIG))
    )

    if document_ids:
        q = q.filter(Document.id.in_(document_ids))

    rows = q.order_by(text("rank DESC")).limit(top_k).all()

    return [{"id": r.id, "title": r.title, "snippet": r.snippet, "rank": round(float(r.rank), 4)} for r in rows]


# ── Tool implementations ─────────────────────────────────────────────────────


def _search_keywords_impl(
    ctx: ToolContext,
    query: str,
    document_ids: list[str] | None = None,
    top_k: int = 5,
) -> ToolResult:
    """Search Document.full_text for keywords using PostgreSQL FTS."""
    t0 = time.perf_counter()
    rows = _execute_fts(ctx.db, ctx.kb_id, query, document_ids=document_ids, top_k=top_k)

    artifacts = [
        Artifact(
            data={
                "doc_id": r["id"],
                "title": r["title"],
                "snippet": r["snippet"],
                "rank": r["rank"],
            },
            source=r["id"],
        )
        for r in rows
    ]

    summary = _build_summary(rows)
    doc_ids = list({r["id"] for r in rows})

    elapsed_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "search_keywords executed",
        query=query[:100],
        kb_id=ctx.kb_id,
        result_count=len(rows),
        latency_ms=round(elapsed_ms, 2),
    )

    return ToolResult(
        summary=summary,
        artifacts=artifacts,
        artifact_count=len(artifacts),
        metadata={"latency_ms": round(elapsed_ms, 2), "documents_scanned": len(rows), "document_ids": doc_ids},
    )


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
        source=document_id,
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
            source=d.id,
        )
        for d in docs
    ]

    lines = [
        f"{i + 1}. UUID={d.id} | title='{d.title}' | format={d.source_format} | size={len(d.full_text)} chars"
        for i, d in enumerate(docs)
    ]
    summary = (
        f"Found {len(docs)} document(s). Use the UUID (not title) with read_document or search_keywords:\n"
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


search_keywords = _ToolDef(
    name="search_keywords",
    description=(
        "Search for keywords or phrases in the full text of documents in the knowledge base. "
        "Returns matching document snippets with ranking scores and their UUID document IDs. "
        "Use this to find specific concepts, terms, or facts across all documents."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords or phrase. Simple text works — no special syntax needed.",
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of document UUIDs to limit the search scope. "
                    "Must be exact UUIDs (e.g. '550e8400-e29b-41d4-a716-446655440000') "
                    "obtained from list_documents or a previous search_keywords call. "
                    "Do NOT pass document titles here."
                ),
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "Number of results to return (default 5).",
            },
        },
        "required": ["query"],
    },
    execute=_search_keywords_impl,
)

read_document = _ToolDef(
    name="read_document",
    description=(
        "Read a specific portion of a document's full text by character offset. "
        "Use search_keywords or list_documents first to obtain the correct document UUID, "
        "then use this tool to read the full surrounding context. "
        "IMPORTANT: document_id must be a UUID, never a document title."
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": (
                    "UUID of the document to read (e.g. '550e8400-e29b-41d4-a716-446655440000'). "
                    "Must be an exact UUID obtained from list_documents or search_keywords results. "
                    "Do NOT pass a document title, filename, or any other string — only a UUID."
                ),
            },
            "offset": {
                "type": "integer",
                "description": "Starting character position (0-based). Default 0 for beginning of document.",
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
        "The returned UUIDs are needed for search_keywords (to scope) and read_document (to read)."
    ),
    parameters={"type": "object", "properties": {}},
    execute=_list_documents_impl,
)

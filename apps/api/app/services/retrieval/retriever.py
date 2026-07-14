"""Hybrid retrieval: pgvector semantic search + PostgreSQL full-text search, fused with RRF.

Both paths query Chunk directly (single table).  ``knowledge_base_id`` is resolved
on Document (not denormalized on Chunk) — doc_ids are scoped to the target KB
before hitting the Chunk table, so no JOIN is needed in the hot path.

FTS uses the ``simple`` config — lowercases and splits on whitespace/punctuation,
making it usable for mixed-language corpora (Chinese, Japanese, Korean alongside
English).  Semantic gaps are covered by the vector path + multi-angle
``lexical_queries`` from the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.telemetry import observe, update_current_span
from app.models.chunk import Chunk
from app.repositories.document import DocumentRepository

if TYPE_CHECKING:
    from app.services.embedding import Embedder

logger = structlog.get_logger(__name__)

# ── FTS config ───────────────────────────────────────────────────────────────
#
# 'simple' does not strip stopwords or apply language-specific stemming — it
# only lowercases and splits on whitespace/punctuation.  This is intentionally
# the same config used by agent tools (tools.py) for Document.full_text.

_FTS_CONFIG = "simple"


# ── Doc ID resolution ────────────────────────────────────────────────────────


def _resolve_doc_ids(
    db: Session,
    *,
    knowledge_base_id: str,
    document_ids: list[str] | None = None,
) -> list[str]:
    """Resolve document IDs scoped to the target knowledge base.

    None  — all documents in the KB
    []    — no documents (empty)
    [...] — filter to the intersection with KB doc IDs (prevents cross-KB leak)
    """
    if document_ids is not None and not document_ids:
        return []

    kb_doc_ids = DocumentRepository.list_ids_by_knowledge_base(db, knowledge_base_id=knowledge_base_id)
    if document_ids is None:
        return kb_doc_ids
    doc_set = set(kb_doc_ids)
    return [d for d in document_ids if d in doc_set]


# ── Vector search ────────────────────────────────────────────────────────────


def _vector_search(
    db: Session,
    *,
    query_embedding: list[float],
    doc_ids: list[str],
    top_k: int,
) -> list[tuple[Chunk, float]]:
    """Cosine similarity search via pgvector — single-table on Chunk."""
    q = (
        db.query(Chunk, Chunk.embedding.cosine_distance(query_embedding).label("score"))
        .filter(Chunk.doc_id.in_(doc_ids))
        .filter(Chunk.embedding.is_not(None))
    )
    rows = q.order_by("score").limit(top_k * 2).all()
    return [(chunk, 1.0 - dist) for chunk, dist in rows]  # distance → similarity


# ── Full-text search (multi-query) ───────────────────────────────────────────


def _fts_search(
    db: Session,
    *,
    query: str,
    doc_ids: list[str],
    top_k: int,
) -> list[tuple[Chunk, float]]:
    """PostgreSQL FTS on Chunk.content with 'simple' config.

    Uses plainto_tsquery for user-friendly search — no tsquery syntax required.
    """
    ts_vector = func.to_tsvector(_FTS_CONFIG, Chunk.content)
    ts_query = func.plainto_tsquery(_FTS_CONFIG, query)

    q = (
        db.query(
            Chunk,
            func.ts_rank(ts_vector, ts_query).label("rank"),
        )
        .filter(Chunk.doc_id.in_(doc_ids))
        .filter(ts_vector.match(query, postgresql_regconfig=_FTS_CONFIG))
    )
    rows = q.order_by(text("rank DESC")).limit(top_k * 2).all()
    return [(chunk, float(rank)) for chunk, rank in rows]


# ── RRF fusion ───────────────────────────────────────────────────────────────


def _rrf_fusion(
    vector_results: list[tuple[Chunk, float]],
    fts_results: list[tuple[Chunk, float]],
    top_k: int = 20,
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    """Reciprocal Rank Fusion — combines two ranked lists into one.

    RRF score = Σ 1 / (k + rank_i) for each result list i.
    An empty list on either side degrades gracefully — the other side's
    ranking takes full effect.
    """
    scores: dict[str, tuple[Chunk, float]] = {}

    for rank, (chunk, _) in enumerate(vector_results):
        scores[chunk.id] = (chunk, 1.0 / (k + rank + 1))

    for rank, (chunk, _) in enumerate(fts_results):
        rrf = 1.0 / (k + rank + 1)
        if chunk.id in scores:
            prev_chunk, prev_score = scores[chunk.id]
            scores[chunk.id] = (prev_chunk, prev_score + rrf)
        else:
            scores[chunk.id] = (chunk, rrf)

    return sorted(scores.values(), key=lambda x: x[1], reverse=True)[:top_k]


# ── Unified result types ─────────────────────────────────────────────────────


@dataclass
class RetrievalResult:
    """Raw results from both retrieval paths with per-path health info.

    Both paths return Chunk entities: FTS hits Chunk.content (tsvector),
    Vector hits Chunk.embedding (pgvector).  Either list may be empty
    (degraded path); both empty + both errors = infrastructure failure.
    """

    fts: list[tuple[Chunk, float]] = field(default_factory=list)
    vector: list[tuple[Chunk, float]] = field(default_factory=list)
    fts_error: str | None = None
    vector_error: str | None = None


@dataclass
class MergedResult:
    """RRF-fused final results with diagnostics.

    When ``chunks`` is empty, callers MUST check ``both_failed``:
    - both_failed=True  → retrieval unavailable, return error to user
    - both_failed=False → retrieval succeeded but no match, hand to CRAG
    """

    chunks: list[tuple[Chunk, float]] = field(default_factory=list)
    both_failed: bool = False
    fts_error: str | None = None
    vector_error: str | None = None


# ── Unified retrieval entry point ────────────────────────────────────────────


@observe(name="search.hybrid", as_type="retriever", capture_input=False, capture_output=False)
def hybrid_retrieve(
    db: Session,
    *,
    semantic_query: str,
    lexical_queries: list[str],
    knowledge_base_id: str,
    embedder: Embedder,
    top_k: int = 20,
    document_ids: list[str] | None = None,
) -> RetrievalResult:
    """Unified hybrid retrieval entry point.

    Two independent paths with different inputs, same target table (Chunk):
    - ``semantic_query``  → embedding → pgvector cosine on Chunk.embedding
    - ``lexical_queries`` → multi-way FTS on Chunk.content (one per phrase)

    Each path fails independently — failure returns [] and records the error;
    the other path continues.  RRF naturally handles empty lists.
    """
    doc_ids = _resolve_doc_ids(db, knowledge_base_id=knowledge_base_id, document_ids=document_ids)

    update_current_span(
        input={
            "semantic_query": semantic_query[:200],
            "lexical_queries": lexical_queries,
            "top_k": top_k,
        },
        metadata={"fts_config": _FTS_CONFIG},
    )

    # ── FTS path (multi-way, independent) ──
    fts_results: list[tuple[Chunk, float]] = []
    fts_error: str | None = None
    if doc_ids:
        try:
            all_fts: dict[str, tuple[Chunk, float]] = {}
            for query in lexical_queries:
                for chunk, score in _fts_search(db, query=query, doc_ids=doc_ids, top_k=top_k):
                    if chunk.id not in all_fts or score > all_fts[chunk.id][1]:
                        all_fts[chunk.id] = (chunk, score)
            fts_results = sorted(all_fts.values(), key=lambda x: x[1], reverse=True)[:top_k]
        except Exception as exc:
            fts_error = str(exc)
            logger.warning("fts search failed, degraded to vector-only", error=fts_error)

    # ── Vector path (single embedding, independent) ──
    vector_results: list[tuple[Chunk, float]] = []
    vector_error: str | None = None
    if doc_ids:
        try:
            query_embedding = embedder.embed([semantic_query])[0]
            vector_results = _vector_search(db, query_embedding=query_embedding, doc_ids=doc_ids, top_k=top_k)
        except Exception as exc:
            vector_error = str(exc)
            logger.warning("vector search failed, degraded to fts-only", error=vector_error)

    if fts_error and vector_error:
        logger.error("both retrieval paths failed", fts_error=fts_error, vector_error=vector_error)

    update_current_span(
        output={
            "fts_count": len(fts_results),
            "vector_count": len(vector_results),
            "fts_error": fts_error is not None,
            "vector_error": vector_error is not None,
        },
    )

    return RetrievalResult(
        fts=fts_results,
        vector=vector_results,
        fts_error=fts_error,
        vector_error=vector_error,
    )


def merge_results(result: RetrievalResult, top_k: int = 20) -> MergedResult:
    """RRF fusion with graceful degradation.

    An empty list on either side degrades naturally — the other side's
    ranking takes full effect.  ``both_failed`` is set only when BOTH
    paths errored (infrastructure failure), not when they returned empty.
    """
    merged = _rrf_fusion(result.vector, result.fts, top_k=top_k)
    both_failed = result.fts_error is not None and result.vector_error is not None

    return MergedResult(
        chunks=merged,
        both_failed=both_failed,
        fts_error=result.fts_error,
        vector_error=result.vector_error,
    )


# ── Compatibility layer (used by existing HybridSearchStrategy) ──────────────


def hybrid_search(
    db: Session,
    *,
    query: str,
    query_embedding: list[float],
    knowledge_base_id: str,
    top_k: int = 10,
    document_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """Legacy entry point — delegates to ``hybrid_retrieve`` + ``merge_results``.

    Kept for backward compatibility with ``HybridSearchStrategy`` and any
    other callers that embed externally.
    """
    doc_ids = _resolve_doc_ids(db, knowledge_base_id=knowledge_base_id, document_ids=document_ids)
    if not doc_ids:
        return []

    vector_results = _vector_search(db, query_embedding=query_embedding, doc_ids=doc_ids, top_k=top_k)
    fts_results = _fts_search(db, query=query, doc_ids=doc_ids, top_k=top_k)
    return _rrf_fusion(vector_results, fts_results, top_k=top_k)

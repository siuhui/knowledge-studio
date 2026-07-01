"""Hybrid retrieval: pgvector semantic search + PostgreSQL full-text search, fused with RRF.

Both paths query Chunk directly (single table) — knowledge_base_id is denormalized
on Chunk to avoid JOINs in the retrieval hot path.
"""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.chunk import Chunk


def _vector_search(
    db: Session,
    *,
    query_embedding: list[float],
    knowledge_base_id: str,
    top_k: int,
    document_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """Cosine similarity search via pgvector — single-table on Chunk."""
    q = (
        db.query(Chunk, Chunk.embedding.cosine_distance(query_embedding).label("score"))
        .filter(Chunk.knowledge_base_id == knowledge_base_id)
        .filter(Chunk.embedding.is_not(None))
    )
    if document_ids is not None:
        q = q.filter(Chunk.doc_id.in_(document_ids))
    rows = q.order_by("score").limit(top_k * 2).all()
    return [(chunk, 1.0 - dist) for chunk, dist in rows]  # distance → similarity


def _keyword_search(
    db: Session,
    *,
    query: str,
    knowledge_base_id: str,
    top_k: int,
    document_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """PostgreSQL full-text search — single-table on Chunk."""
    q = (
        db.query(
            Chunk,
            func.ts_rank(
                func.to_tsvector("english", Chunk.content),
                func.plainto_tsquery("english", query),
            ).label("rank"),
        )
        .filter(Chunk.knowledge_base_id == knowledge_base_id)
        .filter(func.to_tsvector("english", Chunk.content).match(query, postgresql_regconfig="english"))
    )
    if document_ids is not None:
        q = q.filter(Chunk.doc_id.in_(document_ids))
    rows = q.order_by(text("rank DESC")).limit(top_k * 2).all()
    return [(chunk, float(rank)) for chunk, rank in rows]


def rrf_fusion(
    vector_results: list[tuple[Chunk, float]],
    keyword_results: list[tuple[Chunk, float]],
    top_k: int = 10,
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    """Reciprocal Rank Fusion: combines two ranked lists into one.

    RRF score = Σ 1 / (k + rank_i) for each result list i.
    k=60 is a common default that works well in practice.
    """
    scores: dict[str, tuple[Chunk, float]] = {}

    for rank, (chunk, _) in enumerate(vector_results):
        rrf = 1.0 / (k + rank + 1)
        scores[chunk.id] = (chunk, rrf)

    for rank, (chunk, _) in enumerate(keyword_results):
        rrf = 1.0 / (k + rank + 1)
        if chunk.id in scores:
            prev_chunk, prev_score = scores[chunk.id]
            scores[chunk.id] = (prev_chunk, prev_score + rrf)
        else:
            scores[chunk.id] = (chunk, rrf)

    # Sort by RRF score descending
    sorted_results = sorted(scores.values(), key=lambda x: x[1], reverse=True)
    return sorted_results[:top_k]


def hybrid_search(
    db: Session,
    *,
    query: str,
    query_embedding: list[float],
    knowledge_base_id: str,
    top_k: int = 10,
    document_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """Perform hybrid search and return fused results (chunk, score).

    document_ids:
        None  — search all documents
        []    — no documents selected (return empty)
        [...] — filter to these documents
    """
    if document_ids is not None and len(document_ids) == 0:
        return []
    vector_results = _vector_search(
        db,
        query_embedding=query_embedding,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
        document_ids=document_ids,
    )
    keyword_results = _keyword_search(
        db,
        query=query,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
        document_ids=document_ids,
    )
    return rrf_fusion(vector_results, keyword_results, top_k=top_k)

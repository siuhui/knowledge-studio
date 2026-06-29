"""Hybrid retrieval: pgvector semantic search + PostgreSQL full-text search, fused with RRF."""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document


def _vector_search(
    db: Session, *, query_embedding: list[float], knowledge_base_id: str, top_k: int
) -> list[tuple[Chunk, Document, float]]:
    """Cosine similarity search via pgvector."""
    rows = (
        db.query(Chunk, Document, Chunk.embedding.cosine_distance(query_embedding).label("score"))
        .join(Document, Chunk.doc_id == Document.id)
        .filter(Document.knowledge_base_id == knowledge_base_id)
        .filter(Chunk.embedding.is_not(None))
        .order_by("score")
        .limit(top_k * 2)
        .all()
    )
    # cosine_distance returns a value; lower = more similar → convert to similarity score
    results = []
    for chunk, doc, dist in rows:
        score = 1.0 - dist  # convert distance to similarity
        results.append((chunk, doc, score))
    return results


def _keyword_search(
    db: Session, *, query: str, knowledge_base_id: str, top_k: int
) -> list[tuple[Chunk, Document, float]]:
    """PostgreSQL full-text search with ts_rank."""
    rows = (
        db.query(
            Chunk,
            Document,
            func.ts_rank(
                func.to_tsvector("english", Chunk.content),
                func.plainto_tsquery("english", query),
            ).label("rank"),
        )
        .join(Document, Chunk.doc_id == Document.id)
        .filter(Document.knowledge_base_id == knowledge_base_id)
        .filter(func.to_tsvector("english", Chunk.content).match(query, postgresql_regconfig="english"))
        .order_by(text("rank DESC"))
        .limit(top_k * 2)
        .all()
    )
    return [(chunk, doc, float(rank)) for chunk, doc, rank in rows]


def rrf_fusion(
    vector_results: list[tuple[Chunk, Document, float]],
    keyword_results: list[tuple[Chunk, Document, float]],
    top_k: int = 10,
    k: int = 60,
) -> list[tuple[Chunk, Document, float]]:
    """Reciprocal Rank Fusion: combines two ranked lists into one.

    RRF score = Σ 1 / (k + rank_i) for each result list i.
    k=60 is a common default that works well in practice.
    """
    scores: dict[str, tuple[Chunk, Document, float]] = {}

    for rank, (chunk, doc, _) in enumerate(vector_results):
        rrf = 1.0 / (k + rank + 1)
        scores[chunk.id] = (chunk, doc, rrf)

    for rank, (chunk, doc, _) in enumerate(keyword_results):
        rrf = 1.0 / (k + rank + 1)
        if chunk.id in scores:
            prev_chunk, prev_doc, prev_score = scores[chunk.id]
            scores[chunk.id] = (prev_chunk, prev_doc, prev_score + rrf)
        else:
            scores[chunk.id] = (chunk, doc, rrf)

    # Sort by RRF score descending
    sorted_results = sorted(scores.values(), key=lambda x: x[2], reverse=True)
    return sorted_results[:top_k]


def hybrid_search(
    db: Session,
    *,
    query: str,
    query_embedding: list[float],
    knowledge_base_id: str,
    top_k: int = 10,
) -> list[tuple[Chunk, Document, float]]:
    """Perform hybrid search and return fused results."""
    vector_results = _vector_search(
        db,
        query_embedding=query_embedding,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
    )
    keyword_results = _keyword_search(
        db,
        query=query,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
    )
    return rrf_fusion(vector_results, keyword_results, top_k=top_k)

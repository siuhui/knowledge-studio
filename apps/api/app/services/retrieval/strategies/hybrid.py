"""Hybrid search strategy — pgvector cosine + PostgreSQL FTS fused with RRF.

Requires chunks to be embedded.  Best for high-precision semantic search
on knowledge bases that have completed the embed pipeline.
"""

import structlog
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.retrieval.response import RetrievalChunk, RetrievalQueryResponse
from app.services.retrieval.citation_builder import build_citations
from app.services.retrieval.reranker import rerank
from app.services.retrieval.retriever import hybrid_search
from app.services.retrieval.strategies import register

logger = structlog.get_logger(__name__)


def _batch_fetch_documents(db: Session, *, doc_ids: set[str]) -> dict[str, Document]:
    """Fetch Document records by ID for citation/title enrichment."""
    if not doc_ids:
        return {}
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    return {d.id: d for d in docs}


@register("hybrid")
class HybridSearchStrategy:
    """Vector + keyword hybrid search — the original v0.1.0 strategy.

    Calls the embedding API for every query, then runs pgvector cosine
    similarity and PostgreSQL full-text search in parallel, fusing results
    with Reciprocal Rank Fusion.
    """

    def search(
        self,
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
        document_ids: list[str] | None = None,
    ) -> RetrievalQueryResponse:
        # Generate query embedding
        from app.services.embedding import embedder

        query_embedding = embedder.embed([query])[0]

        # Hybrid search — single-table on Chunk (zero JOIN)
        chunk_scores = hybrid_search(
            db,
            query=query,
            query_embedding=query_embedding,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            document_ids=document_ids,
        )

        if not chunk_scores:
            return RetrievalQueryResponse(query=query, results=[])

        # Re-rank
        chunk_scores = rerank(chunk_scores)

        # Batch-fetch documents for titles (top_k items, PK lookup)
        doc_ids = {c.doc_id for c, _ in chunk_scores}
        docs = _batch_fetch_documents(db, doc_ids=doc_ids)

        # Build response with (Chunk, Document, score) for citations
        results_with_docs = []
        retrieval_chunks = []
        for chunk, score in chunk_scores:
            doc = docs.get(chunk.doc_id)
            if doc is None:
                continue
            results_with_docs.append((chunk, doc, score))
            retrieval_chunks.append(
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
            "hybrid retrieval completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            result_count=len(retrieval_chunks),
        )

        return RetrievalQueryResponse(query=query, results=retrieval_chunks)

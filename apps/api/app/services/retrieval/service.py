"""Retrieval service: orchestrates search and QA."""

import structlog
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.retrieval.response import QaResponse, RetrievalChunk, RetrievalQueryResponse
from app.services.retrieval.citation_builder import build_citations
from app.services.retrieval.reranker import rerank
from app.services.retrieval.retriever import hybrid_search

logger = structlog.get_logger(__name__)


def _batch_fetch_documents(db: Session, *, doc_ids: set[str]) -> dict[str, Document]:
    """Fetch Document records by ID for citation/title enrichment."""
    if not doc_ids:
        return {}
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    return {d.id: d for d in docs}


class RetrievalService:
    @staticmethod
    def search(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
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
                    citation=build_citations([(chunk, doc, score)])[0],
                )
            )

        logger.info(
            "retrieval completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            result_count=len(retrieval_chunks),
        )

        return RetrievalQueryResponse(query=query, results=retrieval_chunks)

    @staticmethod
    def ask(
        db: Session,
        *,
        query: str,
        knowledge_base_id: str,
        top_k: int = 10,
    ) -> QaResponse:
        """RAG QA: retrieve → build context → answer with citations."""
        # Retrieve
        retrieval = RetrievalService.search(db, query=query, knowledge_base_id=knowledge_base_id, top_k=top_k)

        if not retrieval.results:
            return QaResponse(
                query=query,
                answer="I couldn't find any relevant information to answer your question.",
                sources=[],
            )

        # Build context from retrieved chunks
        context_parts = []
        for result in retrieval.results:
            context_parts.append(f"[Source: {result.document_title}]\n{result.content}")
        context = "\n\n".join(context_parts)

        # Call LLM for answer
        from app.services.llm import llm_provider

        answer = llm_provider.answer(query=query, context=context)

        # Build citations
        citations = []
        seen = set()
        for result in retrieval.results:
            doc_id = result.citation.document_id
            if doc_id in seen:
                continue
            seen.add(doc_id)
            citations.append(result.citation)

        logger.info(
            "qa completed",
            query=query[:100],
            knowledge_base_id=knowledge_base_id,
            source_count=len(citations),
        )

        return QaResponse(query=query, answer=answer, sources=citations)

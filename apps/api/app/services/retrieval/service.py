"""Retrieval service: orchestrates search and QA."""

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.services.retrieval.citation_builder import build_citations
from app.services.retrieval.reranker import rerank
from app.services.retrieval.retriever import hybrid_search
from app.schemas.retrieval.response import QaResponse, RetrievalChunk, RetrievalQueryResponse

logger = structlog.get_logger(__name__)


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

        # Hybrid search
        results = hybrid_search(
            db,
            query=query,
            query_embedding=query_embedding,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
        )

        # Re-rank
        results = rerank(results)

        # Build response
        retrieval_chunks = [
            RetrievalChunk(
                chunk_id=chunk.id,
                content=chunk.content,
                score=score,
                document_title=doc.title,
                citation=build_citations([(chunk, doc, score)])[0],
            )
            for chunk, doc, score in results
        ]

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
        retrieval = RetrievalService.search(
            db, query=query, knowledge_base_id=knowledge_base_id, top_k=top_k
        )

        if not retrieval.results:
            return QaResponse(
                query=query,
                answer="I couldn't find any relevant information to answer your question.",
                sources=[],
            )

        # Build context from retrieved chunks
        context_parts = []
        for result in retrieval.results:
            context_parts.append(
                f"[Source: {result.document_title}]\n{result.content}"
            )
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

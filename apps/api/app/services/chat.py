from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.schemas.chat import ChatResponse
from app.schemas.retrieval.citation import Citation
from app.schemas.retrieval.response import RetrievalQueryResponse
from app.services.llm import llm_provider
from app.services.retrieval.service import RetrievalService
from app.services.session import SessionService

logger = structlog.get_logger(__name__)

RAG_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Always cite the source document when using information from the context. "
    "If the context doesn't contain enough information to answer, say so clearly."
)

CHAT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question concisely and accurately."
)


def _build_citations(retrieval: RetrievalQueryResponse | None) -> list[dict[str, Any]]:
    """Extract deduplicated citations from retrieval results."""
    if not retrieval or not retrieval.results:
        return []
    seen: set[str] = set()
    citations: list[dict[str, Any]] = []
    for result in retrieval.results:
        cid = result.citation.document_id
        if cid not in seen:
            seen.add(cid)
            citations.append(result.citation.model_dump())
    return citations


def _build_context(retrieval: RetrievalQueryResponse | None) -> str:
    """Build RAG context string from retrieval results."""
    if not retrieval or not retrieval.results:
        return ""
    return "\n\n".join(
        f"[Source: {r.document_title}]\n{r.content}" for r in retrieval.results
    )


class ChatService:
    @staticmethod
    def send_message(
        db: Session,
        *,
        kb_id: str,
        user_id: str,
        session_id: str | None,
        content: str,
        reference_document_ids: list[str] | None = None,
    ) -> ChatResponse:
        """Send a chat message. Auto-creates session if session_id is None.

        reference_document_ids from the request takes priority.
        When omitted, falls back to the session's stored value.
        None=all, []=none, [...] =filter.
        """

        doc_ids = reference_document_ids  # request takes priority

        # 1. Resolve session (create if new, with the correct scope)
        if session_id is None:
            session = SessionService.create(
                db, kb_id=kb_id, user_id=user_id,
                reference_document_ids=doc_ids,
            )
            session_id = session.id
        else:
            session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)
            if reference_document_ids is None:
                doc_ids = session.reference_document_ids  # fall back to stored scope

        # 2. Retrieve — skip when no documents are explicitly selected
        if doc_ids is not None and len(doc_ids) == 0:
            retrieval = None
        else:
            retrieval = RetrievalService.search(
                db,
                query=content,
                knowledge_base_id=kb_id,
                top_k=10,
                document_ids=doc_ids,
            )

        context = _build_context(retrieval)

        # 3. Build messages with conversation history
        # session.messages is eager-loaded (lazy="selectin"), sorted by created_at
        history: list[dict[str, str]] = [
            {"role": m.role, "content": m.content} for m in session.messages
        ]

        if context:
            system_prompt = RAG_SYSTEM_PROMPT
            user_message = f"Context:\n{context}\n\nQuestion: {content}"
        else:
            system_prompt = CHAT_SYSTEM_PROMPT
            user_message = content

        messages = [*history, {"role": "user", "content": user_message}]
        answer = llm_provider.generate(system_prompt=system_prompt, messages=messages)

        # 4. Build citations & persist
        citations = _build_citations(retrieval)

        persisted = True
        ai_msg_id = ""
        try:
            _, _, ai_msg = SessionService.add_qa_exchange(
                db,
                session_id=session_id,
                kb_id=kb_id,
                user_id=user_id,
                query=content,
                answer=answer,
                citations=citations,
            )
            ai_msg_id = ai_msg.id
        except Exception:
            logger.exception("failed to persist messages", session_id=session_id)
            persisted = False

        return ChatResponse(
            session_id=session_id,
            message_id=ai_msg_id,
            answer=answer,
            citations=[Citation(**c) for c in citations],
            persisted=persisted,
        )

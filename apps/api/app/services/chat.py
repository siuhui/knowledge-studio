import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.telemetry import get_current_trace_id, observe, trace_context, update_current_span
from app.models.chat_message import ChatMessage
from app.repositories.message import MessageRepository
from app.repositories.session import SessionRepository
from app.schemas.chat import ChatResponse
from app.schemas.retrieval.citation import Citation
from app.schemas.retrieval.response import RetrievalQueryResponse
from app.services.llm import get_async_provider, llm_provider
from app.services.retrieval.service import RetrievalService
from app.services.session import DEFAULT_SESSION_TITLE, SessionService, auto_title

logger = structlog.get_logger(__name__)

RAG_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Always cite the source document when using information from the context. "
    "If the context doesn't contain enough information to answer, say so clearly."
)

CHAT_SYSTEM_PROMPT = "You are a helpful assistant. Answer the user's question concisely and accurately."


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
    return "\n\n".join(f"[Source: {r.document_title}]\n{r.content}" for r in retrieval.results)


class ChatService:
    @staticmethod
    @observe(name="chat.message", capture_input=False, capture_output=False)
    def send_message(
        db: Session,
        *,
        kb_id: str,
        user_id: str,
        session_id: str | None,
        content: str,
        reference_document_ids: list[str] | None = None,
        search_strategy: str = "agentic",
    ) -> ChatResponse:
        """Send a chat message. Auto-creates session if session_id is None.

        LLM generation is auto-traced by ``langfuse.openai`` integration.
        """
        doc_ids = reference_document_ids

        # Explicitly set trace input to only the relevant user query
        update_current_span(
            input={"query": content, "kb_id": kb_id, "strategy": search_strategy},
        )

        # 1. Resolve session (outside trace_context so new sessions get real IDs)
        if session_id is None:
            session = SessionService.create(db, kb_id=kb_id, user_id=user_id, reference_document_ids=doc_ids)
            session_id = session.id
        else:
            session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)
            if reference_document_ids is None:
                doc_ids = session.reference_document_ids

        with trace_context(
            user_id=user_id,
            session_id=session_id,
            tags=["chat", "sync"],
        ):
            # 2. Retrieve (auto-traced via @observe on RetrievalService.search)
            if doc_ids is not None and len(doc_ids) == 0:
                retrieval = None
            else:
                retrieval = RetrievalService.search(
                    db,
                    query=content,
                    knowledge_base_id=kb_id,
                    top_k=10,
                    document_ids=doc_ids,
                    strategy=search_strategy,
                )

            # 3. Build context + messages
            context = _build_context(retrieval)
            history: list[dict[str, str]] = [{"role": m.role, "content": m.content} for m in session.messages]

            if context:
                system_prompt = RAG_SYSTEM_PROMPT
                user_message = f"Context:\n{context}\n\nQuestion: {content}"
            else:
                system_prompt = CHAT_SYSTEM_PROMPT
                user_message = content

            messages = [*history, {"role": "user", "content": user_message}]

            # 4. LLM generation (auto-traced via langfuse.openai)
            answer = llm_provider.generate(system_prompt=system_prompt, messages=messages)

            # 5. Persist
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

            # Set trace output with a concise summary
            update_current_span(
                output={"answer_length": len(answer), "persisted": persisted, "citations_count": len(citations)},
            )

            return ChatResponse(
                session_id=session_id,
                message_id=ai_msg_id,
                answer=answer,
                citations=[Citation(**c) for c in citations],
                persisted=persisted,
            )

    @staticmethod
    @observe(name="chat.message.stream", capture_input=False, capture_output=False)
    async def stream_message(
        db: Session,
        *,
        kb_id: str,
        user_id: str,
        session_id: str | None,
        content: str,
        reference_document_ids: list[str] | None = None,
        search_strategy: str = "agentic",
    ) -> AsyncIterator[str]:
        """Stream chat response as SSE JSON event strings.

        LLM generation is auto-traced by ``langfuse.openai`` integration.
        """
        doc_ids = reference_document_ids

        update_current_span(
            input={"query": content, "kb_id": kb_id, "strategy": search_strategy},
        )

        # ── 1. Resolve session (outside trace_context so new sessions get real IDs) ──
        try:
            if session_id is None:
                session = SessionService.create(db, kb_id=kb_id, user_id=user_id, reference_document_ids=doc_ids)
                session_id = session.id
            else:
                session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)
                if reference_document_ids is None:
                    doc_ids = session.reference_document_ids
        except AppError as e:
            logger.warning("session lookup failed", session_id=session_id, error=str(e))
            yield json.dumps({"type": "error", "message": e.message})
            yield json.dumps({"type": "done", "persisted": False, "ai_message_id": ""})
            return

        with trace_context(
            user_id=user_id,
            session_id=session_id,
            tags=["chat", "stream"],
        ):
            try:
                # ── 1. History before persisting ──
                history: list[dict[str, str]] = [{"role": m.role, "content": m.content} for m in session.messages]

                # ── 2. Persist user message ──
                user_msg = ChatMessage(role="user", content=content)
                session.messages.append(user_msg)
                MessageRepository.save(db, message=user_msg)
                db.commit()

                now = datetime.now(UTC)
                if session.title == DEFAULT_SESSION_TITLE:
                    session.title = auto_title(content)
                session.last_message_at = now
                SessionRepository.save(db, session=session)
                db.commit()

                trace_id = get_current_trace_id()

                yield json.dumps(
                    {
                        "type": "session",
                        "session_id": session_id,
                        "user_msg_id": user_msg.id,
                        "trace_id": trace_id,
                    }
                )

                # ── 3. Retrieve (auto-traced via @observe on RetrievalService.search) ──
                if doc_ids is not None and len(doc_ids) == 0:
                    retrieval = None
                else:
                    retrieval = RetrievalService.search(
                        db,
                        query=content,
                        knowledge_base_id=kb_id,
                        top_k=10,
                        document_ids=doc_ids,
                        strategy=search_strategy,
                    )

                if retrieval and retrieval.agent_steps:
                    for step in retrieval.agent_steps:
                        yield json.dumps(step)

                context = _build_context(retrieval)

                # ── 4. Build messages ──
                if context:
                    system_prompt = RAG_SYSTEM_PROMPT
                    user_message = f"Context:\n{context}\n\nQuestion: {content}"
                else:
                    system_prompt = CHAT_SYSTEM_PROMPT
                    user_message = content

                messages = [*history, {"role": "user", "content": user_message}]

                # ── 5. Stream LLM (auto-traced via langfuse.openai) ──
                full_answer = ""
                async_provider = get_async_provider()

                async for token in async_provider.generate_stream(system_prompt=system_prompt, messages=messages):
                    full_answer += token
                    yield json.dumps({"type": "token", "text": token})

                # ── 6. Citations ──
                citations = _build_citations(retrieval)
                yield json.dumps({"type": "citation", "citations": citations})

                # ── 7. Persist AI message ──
                persisted = True
                ai_msg_id = ""
                try:
                    ai_msg = ChatMessage(
                        role="assistant",
                        content=full_answer,
                        citations=citations,
                    )
                    session.messages.append(ai_msg)
                    MessageRepository.save(db, message=ai_msg)
                    db.commit()
                    ai_msg_id = ai_msg.id
                except Exception:
                    db.rollback()
                    logger.exception("failed to persist AI message", session_id=session_id)
                    persisted = False

                # Set trace output with a concise summary
                update_current_span(
                    output={
                        "answer_length": len(full_answer),
                        "persisted": persisted,
                        "citations_count": len(citations),
                    },
                )

                yield json.dumps({"type": "done", "persisted": persisted, "ai_message_id": ai_msg_id})

            except Exception:
                logger.exception("stream error", session_id=session_id)
                update_current_span(
                    level="ERROR",
                    status_message="An error occurred during generation",
                )
                yield json.dumps({"type": "error", "message": "An error occurred during generation"})
                yield json.dumps({"type": "done", "persisted": False})

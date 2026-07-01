import re
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.core.response_codes import ResponseCode
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.services.knowledge_base import KnowledgeBaseService

logger = structlog.get_logger(__name__)

_MAX_TITLE_LENGTH = 60


def _auto_title(query: str) -> str:
    """Derive session title from first user query."""
    cleaned = re.sub(r"\s+", " ", query.strip())
    if len(cleaned) <= _MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[:_MAX_TITLE_LENGTH].rstrip() + "..."


class SessionService:
    @staticmethod
    def create(
        db: Session,
        *,
        kb_id: str,
        user_id: str,
        title: str = "New Chat",
        reference_document_ids: list[str] | None = None,
    ) -> ChatSession:
        # Verify KB ownership
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=kb_id, user_id=user_id)

        session = ChatSession(
            knowledge_base_id=kb_id,
            user_id=user_id,
            title=title,
            reference_document_ids=reference_document_ids,
        )
        session = SessionRepository.save(db, session=session)
        logger.info(
            "chat_session created",
            session_id=session.id,
            knowledge_base_id=kb_id,
            user_id=user_id,
        )
        return session

    @staticmethod
    def get_by_id(
        db: Session,
        *,
        session_id: str,
        kb_id: str,
        user_id: str,
    ) -> ChatSession:
        # Verify KB ownership first
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=kb_id, user_id=user_id)

        session = SessionRepository.get_by_id(db, session_id=session_id)
        if not session:
            raise NotFoundError(
                code=ResponseCode.SESSION_NOT_FOUND,
                message=f"Session {session_id} not found",
            )
        if session.knowledge_base_id != kb_id:
            raise ForbiddenError(
                code=ResponseCode.SESSION_ACCESS_DENIED,
                message="Access denied",
            )
        return session

    @staticmethod
    def list_by_kb(
        db: Session,
        *,
        kb_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ChatSession], int]:
        # Verify KB ownership
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=kb_id, user_id=user_id)

        offset = (page - 1) * page_size
        return SessionRepository.list_by_knowledge_base(db, kb_id=kb_id, offset=offset, limit=page_size)

    @staticmethod
    def update(
        db: Session,
        *,
        session_id: str,
        kb_id: str,
        user_id: str,
        title: str | None = None,
        update_doc_ids: bool = False,
        reference_document_ids: list[str] | None = None,
    ) -> ChatSession:
        session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)
        if title is not None:
            session.title = title
        if update_doc_ids:
            session.reference_document_ids = reference_document_ids
        SessionRepository.save(db, session=session)
        logger.info("chat_session updated", session_id=session_id)
        return session

    @staticmethod
    def delete(
        db: Session,
        *,
        session_id: str,
        kb_id: str,
        user_id: str,
    ) -> None:
        session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)
        SessionRepository.delete(db, session=session)
        logger.info("chat_session deleted", session_id=session_id)

    @staticmethod
    def add_qa_exchange(
        db: Session,
        *,
        session_id: str,
        kb_id: str,
        user_id: str,
        query: str,
        answer: str,
        citations: list[dict[str, object]] | None = None,
    ) -> tuple[ChatSession, ChatMessage, ChatMessage]:
        """Persist user message + assistant message. Auto-name session if first message."""
        session = SessionService.get_by_id(db, session_id=session_id, kb_id=kb_id, user_id=user_id)

        now = datetime.now(UTC)

        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=query,
        )
        MessageRepository.save(db, message=user_msg)

        ai_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=answer,
            citations=citations,
        )
        MessageRepository.save(db, message=ai_msg)

        # Update last_message_at
        session.last_message_at = now

        # Auto-name session if title is still default
        if session.title == "New Chat":
            session.title = _auto_title(query)

        SessionRepository.save(db, session=session)

        logger.info(
            "qa exchange persisted",
            session_id=session_id,
            user_msg_id=user_msg.id,
            ai_msg_id=ai_msg.id,
        )
        return session, user_msg, ai_msg

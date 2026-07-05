from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


class SessionRepository:
    @staticmethod
    def get_by_id(db: Session, *, session_id: str) -> ChatSession | None:
        return db.get(ChatSession, session_id)

    @staticmethod
    def list_by_knowledge_base(
        db: Session, *, kb_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[ChatSession], int]:
        """List sessions with COUNT(messages) to avoid N+1."""
        query = (
            db.query(
                ChatSession,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.knowledge_base_id == kb_id)
            .group_by(ChatSession.id)
        )
        subq = query.subquery()
        total_q = db.query(func.count()).select_from(subq)
        total = total_q.scalar() or 0
        items_q = db.query(subq).order_by(subq.c.last_message_at.desc().nullslast()).offset(offset).limit(limit)
        rows = items_q.all()
        sessions = []
        for row in rows:
            session_dict = {k: v for k, v in row._asdict().items() if k != "message_count"}
            session = ChatSession(**session_dict)
            session._message_count = row.message_count  # type: ignore[attr-defined]
            sessions.append(session)
        return sessions, total

    @staticmethod
    def save(db: Session, *, session: ChatSession) -> ChatSession:
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def delete(db: Session, *, session: ChatSession) -> None:
        db.delete(session)
        db.flush()

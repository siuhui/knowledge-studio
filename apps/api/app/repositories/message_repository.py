from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage


class MessageRepository:
    @staticmethod
    def save(db: Session, *, message: ChatMessage) -> ChatMessage:
        db.add(message)
        db.flush()
        return message

    @staticmethod
    def list_by_session(
        db: Session, *, session_id: str, offset: int = 0, limit: int = 200
    ) -> tuple[list[ChatMessage], int]:
        query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
        total = query.count()
        items = query.order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
        return items, total

from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    @staticmethod
    def get_by_id(db: Session, *, knowledge_base_id: str) -> KnowledgeBase | None:
        return db.get(KnowledgeBase, knowledge_base_id)

    @staticmethod
    def list_by_user(db: Session, *, user_id: str, offset: int = 0, limit: int = 20) -> tuple[list[KnowledgeBase], int]:
        query = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id)
        total = query.count()
        items = query.order_by(KnowledgeBase.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def save(db: Session, *, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        db.add(knowledge_base)
        db.flush()
        return knowledge_base

    @staticmethod
    def delete(db: Session, *, knowledge_base: KnowledgeBase) -> None:
        db.delete(knowledge_base)
        db.flush()

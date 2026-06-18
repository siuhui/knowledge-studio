from sqlalchemy.orm import Session

from app.models.source import Source


class SourceRepository:
    @staticmethod
    def get_by_id(db: Session, *, source_id: str) -> Source | None:
        return db.get(Source, source_id)

    @staticmethod
    def list_by_knowledge_base(
        db: Session, *, knowledge_base_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[Source], int]:
        query = db.query(Source).filter(Source.knowledge_base_id == knowledge_base_id)
        total = query.count()
        items = query.order_by(Source.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def save(db: Session, *, source: Source) -> Source:
        db.add(source)
        db.flush()
        return source

    @staticmethod
    def delete(db: Session, *, source: Source) -> None:
        db.delete(source)
        db.flush()

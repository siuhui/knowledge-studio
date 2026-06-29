from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    @staticmethod
    def get_by_id(db: Session, *, document_id: str) -> Document | None:
        return db.get(Document, document_id)

    @staticmethod
    def get_by_text_hash(db: Session, *, text_hash: str) -> Document | None:
        return db.query(Document).filter(Document.text_hash == text_hash).first()

    @staticmethod
    def list_by_source(db: Session, *, source_id: str, offset: int = 0, limit: int = 20) -> tuple[list[Document], int]:
        query = db.query(Document).filter(Document.source_id == source_id)
        total = query.count()
        items = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def list_by_knowledge_base(
        db: Session, *, knowledge_base_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[Document], int]:
        query = db.query(Document).filter(Document.knowledge_base_id == knowledge_base_id)
        total = query.count()
        items = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def save(db: Session, *, document: Document) -> Document:
        db.add(document)
        db.flush()
        return document

    @staticmethod
    def delete(db: Session, *, document: Document) -> None:
        db.delete(document)
        db.flush()

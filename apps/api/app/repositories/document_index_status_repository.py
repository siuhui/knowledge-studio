"""DocumentIndexStatus repository — 1:1 extension to Document for indexing lifecycle."""

from sqlalchemy.orm import Session

from app.models.document_index_status import DocumentIndexStatus


class DocumentIndexStatusRepository:
    @staticmethod
    def get_by_document(db: Session, *, document_id: str) -> DocumentIndexStatus | None:
        return db.query(DocumentIndexStatus).filter(DocumentIndexStatus.document_id == document_id).first()

    @staticmethod
    def get_or_create(db: Session, *, document_id: str) -> DocumentIndexStatus:
        existing = DocumentIndexStatusRepository.get_by_document(db, document_id=document_id)
        if existing:
            return existing
        status = DocumentIndexStatus(document_id=document_id)
        db.add(status)
        db.flush()
        return status

    @staticmethod
    def save(db: Session, *, status: DocumentIndexStatus) -> DocumentIndexStatus:
        db.merge(status)
        db.flush()
        return status

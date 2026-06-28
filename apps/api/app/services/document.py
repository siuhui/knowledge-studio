import hashlib

import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository

logger = structlog.get_logger(__name__)

SUPPORTED_FORMATS = {"pdf", "markdown", "text"}


class DocumentService:
    @staticmethod
    def create_document(
        db: Session,
        *,
        source_id: str,
        title: str,
        source_format: str,
        content: str,
        path: str | None = None,
    ) -> Document:
        if source_format not in SUPPORTED_FORMATS:
            raise ValidationError(
                code=ResponseCode.DOCUMENT_UNSUPPORTED_FORMAT,
                message=f"Format '{source_format}' is not supported. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
            )

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Check for duplicate content
        existing = DocumentRepository.get_by_content_hash(db, content_hash=content_hash)
        if existing:
            logger.info(
                "document content unchanged, skipping",
                document_id=existing.id,
                content_hash=content_hash,
            )
            return existing

        document = Document(
            source_id=source_id,
            title=title,
            path=path,
            source_format=source_format,
            content=content,
            content_hash=content_hash,
            status="active",
        )
        document = DocumentRepository.save(db, document=document)
        logger.info("document created", document_id=document.id, title=title)
        return document

    @staticmethod
    def get_by_id(db: Session, *, document_id: str) -> Document:
        document = DocumentRepository.get_by_id(db, document_id=document_id)
        if not document:
            raise NotFoundError(
                code=ResponseCode.DOCUMENT_NOT_FOUND,
                message=f"Document {document_id} not found",
            )
        return document

    @staticmethod
    def delete(db: Session, *, document_id: str) -> None:
        document = DocumentService.get_by_id(db, document_id=document_id)
        DocumentRepository.delete(db, document=document)
        logger.info("document deleted", document_id=document_id)

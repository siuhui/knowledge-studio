import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.response_codes import ResponseCode
from app.models.document import Document
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.knowledge_base import KnowledgeBaseService
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

MAX_DOCUMENT_DETAIL_CHUNKS = 1000


class DocumentService:
    """Document metadata operations.

    Full parsed text is persisted in Document.full_text so re-chunking
    doesn't require re-parsing the original file.  Indexing happens in
    services/index_pipeline.py.

    Ownership is verified through the Document → Source → KnowledgeBase chain:
    every method that accesses a document requires the requesting user_id
    to match knowledge_base.user_id.
    """

    @staticmethod
    def get_by_id(db: Session, *, document_id: str, user_id: str) -> "Document":
        """Get a document by ID, verifying ownership via document.knowledge_base_id."""
        document = DocumentRepository.get_by_id(db, document_id=document_id)
        if not document:
            raise NotFoundError(
                code=ResponseCode.DOCUMENT_NOT_FOUND,
                message=f"Document {document_id} not found",
            )
        # Verify ownership directly via document.knowledge_base_id
        # (does not depend on source, works for orphaned documents too)
        KnowledgeBaseService.get_by_id(
            db,
            knowledge_base_id=document.knowledge_base_id,
            user_id=user_id,
        )
        return document

    @staticmethod
    def list_by_knowledge_base(
        db: Session,
        *,
        knowledge_base_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list["Document"], int]:
        """List all documents for a knowledge base, including orphaned ones."""
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)
        return DocumentRepository.list_by_knowledge_base(
            db, knowledge_base_id=knowledge_base_id, offset=offset, limit=limit
        )

    @staticmethod
    def list_by_source(
        db: Session,
        *,
        source_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list["Document"], int]:
        """List documents for a source with ownership verification."""
        SourceService.get_by_id(db, source_id=source_id, user_id=user_id)
        return DocumentRepository.list_by_source(db, source_id=source_id, offset=offset, limit=limit)

    @staticmethod
    def get_chunks(db: Session, *, document_id: str, user_id: str) -> dict:
        """Get document metadata and its indexed chunks.

        Returns chunk content in order so the frontend can render a continuous
        document reader.  Truncates at MAX_DOCUMENT_DETAIL_CHUNKS to bound
        response size.
        """
        document = DocumentService.get_by_id(db, document_id=document_id, user_id=user_id)
        all_chunks = ChunkRepository.list_by_document(db, document_id=document_id)

        truncated = len(all_chunks) > MAX_DOCUMENT_DETAIL_CHUNKS
        chunks = all_chunks[:MAX_DOCUMENT_DETAIL_CHUNKS]

        return {
            "document": document,
            "chunks": chunks,
            "total_count": len(all_chunks),
            "truncated": truncated,
        }

    @staticmethod
    def delete(db: Session, *, document_id: str, user_id: str) -> None:
        """Delete a document and its chunks (cascade)."""
        document = DocumentService.get_by_id(db, document_id=document_id, user_id=user_id)
        DocumentRepository.delete(db, document=document)
        logger.info("document deleted", document_id=document_id)

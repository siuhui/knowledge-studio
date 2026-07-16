import hashlib
from typing import TypedDict

import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.response_codes import ResponseCode
from app.core.telemetry import observe, update_current_span
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.status_enums import DocumentStatus
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.services.knowledge_base import KnowledgeBaseService
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

MAX_DOCUMENT_DETAIL_CHUNKS = 1000


class DocumentChunksResult(TypedDict):
    document: Document
    chunks: list[Chunk]
    total_count: int
    truncated: bool


class DocumentService:
    """Document CRUD — creation, retrieval, deletion, and chunk access.

    Full parsed text is persisted in Document.full_text so re-chunking
    doesn't require re-parsing the original file.  Indexing happens in
    services/index_pipeline.py.

    Ownership is verified through the Document → Source → KnowledgeBase chain:
    every method that accesses a document requires the requesting user_id
    to match knowledge_base.user_id.
    """

    @staticmethod
    @observe(name="ingestion.create_document", capture_input=False, capture_output=False)
    def create(
        db: Session,
        *,
        full_text: str,
        title: str,
        source_format: str,
        source_id: str | None,
        kb_id: str,
        path: str | None = None,
    ) -> str:
        """Create a Document from extracted text.

        Creates a PROCESSING placeholder first, then fills content and
        transitions to READY. Deduplicates by text_hash within the same KB —
        returns the existing document_id if a match is found.

        ``source_id`` is nullable — it matches Document's own SET-NULL column.
        The normal ingestion flow always supplies a Source, but callers that
        bypass upload/URL ingestion (e.g. eval-corpus seeding) may pass None;
        ``knowledge_base_id`` is the canonical KB reference regardless.
        """
        update_current_span(
            input={"title": title, "source_format": source_format, "source_id": source_id, "kb_id": kb_id},
        )

        document = Document(
            source_id=source_id,
            knowledge_base_id=kb_id,
            title=title,
            path=path,
            source_format=source_format,
            full_text="",
            text_hash="",
            status=DocumentStatus.PROCESSING,
        )
        document = DocumentRepository.save(db, document=document)

        if not full_text.strip():
            logger.warning("extracted text is empty", title=title)

        text_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        existing = DocumentRepository.get_by_text_hash(db, text_hash=text_hash, knowledge_base_id=kb_id)
        if existing and existing.id != document.id:
            logger.info("text hash match, removing duplicate", document_id=existing.id, title=title)
            DocumentRepository.delete(db, document=document)
            update_current_span(output={"document_id": existing.id, "dedup": True})
            return existing.id

        document.full_text = full_text
        document.text_hash = text_hash
        document.status = DocumentStatus.READY
        DocumentRepository.save(db, document=document)

        logger.info("document created", document_id=document.id, text_length=len(full_text))
        update_current_span(output={"document_id": document.id})
        return document.id

    @staticmethod
    def get_by_id(db: Session, *, document_id: str, user_id: str) -> Document:
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
    ) -> tuple[list[Document], int]:
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
    ) -> tuple[list[Document], int]:
        """List documents for a source with ownership verification."""
        SourceService.get_by_id(db, source_id=source_id, user_id=user_id)
        return DocumentRepository.list_by_source(db, source_id=source_id, offset=offset, limit=limit)

    @staticmethod
    def get_chunks(db: Session, *, document_id: str, user_id: str) -> DocumentChunksResult:
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

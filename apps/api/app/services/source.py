import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.models.source import Source
from app.models.status_enums import SourceStatus
from app.repositories.source_repository import SourceRepository
from app.services.knowledge_base import KnowledgeBaseService
from app.services.object_storage import ObjectStorageService

logger = structlog.get_logger(__name__)

SUPPORTED_SOURCE_TYPES = {"upload"}  # v0.1.0 only upload


class SourceService:
    @staticmethod
    def create(
        db: Session,
        *,
        knowledge_base_id: str,
        user_id: str,
        type: str = "upload",
        config: dict[str, object] | None = None,
    ) -> Source:
        # Verify ownership
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)

        if type not in SUPPORTED_SOURCE_TYPES:
            raise ValidationError(
                code=ResponseCode.SOURCE_TYPE_UNSUPPORTED,
                message=f"Source type '{type}' is not supported in v0.1.0",
            )

        source = Source(
            knowledge_base_id=knowledge_base_id,
            type=type,
            config=config or {},
        )
        source = SourceRepository.save(db, source=source)
        logger.info(
            "source created",
            source_id=source.id,
            knowledge_base_id=knowledge_base_id,
        )
        return source

    @staticmethod
    def update_config_and_activate(
        db: Session,
        *,
        source_id: str,
        config: dict[str, object],
    ) -> Source:
        """Update source config and transition pending -> active."""
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
        if source.status != SourceStatus.PENDING:
            raise ValidationError(
                code=ResponseCode.SOURCE_STATUS_INVALID,
                message=f"Cannot complete upload: source is already {source.status}",
            )
        source.config = config
        source.status = SourceStatus.ACTIVE
        SourceRepository.save(db, source=source)
        logger.info("source activated", source_id=source_id)
        return source

    @staticmethod
    def mark_invalid(*, source_id: str) -> None:
        """Mark a source as invalid (config stale or resource unreachable).

        Creates its own DB session — safe for background tasks.
        """
        from app.database import SessionLocal

        with SessionLocal() as db:
            with db.begin():
                source = db.get(Source, source_id)
                if source and source.status != SourceStatus.INVALID:
                    source.status = SourceStatus.INVALID
                    logger.info("source marked as invalid", source_id=source_id)

    @staticmethod
    def get_by_id(db: Session, *, source_id: str, user_id: str) -> Source:
        """Get a source by ID, verifying the requesting user owns its knowledge base."""
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
        # Verify ownership: raises ForbiddenError if user doesn't own the KB
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=source.knowledge_base_id, user_id=user_id)
        return source

    @staticmethod
    def list_by_knowledge_base(
        db: Session,
        *,
        knowledge_base_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Source], int]:
        # Verify ownership: raises ForbiddenError if user doesn't own the KB
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)
        offset = (page - 1) * page_size
        return SourceRepository.list_by_knowledge_base(
            db, knowledge_base_id=knowledge_base_id, offset=offset, limit=page_size
        )

    @staticmethod
    def delete(db: Session, *, source_id: str, user_id: str) -> None:
        """Delete a source and its MinIO objects.

        Documents are preserved — the DB sets document.source_id = NULL
        via the FK ON DELETE SET NULL constraint. Only the ingestion
        artifact is removed; extracted documents and chunks survive.

        Deletes the DB record first (so the transaction can roll back if
        it fails), then does best-effort MinIO prefix cleanup.

        Uses delete_prefix based on source_id — catches all objects
        uploaded for this source, including failed/partial uploads.
        """
        source = SourceService.get_by_id(db, source_id=source_id, user_id=user_id)

        prefix = f"uploads/{source.knowledge_base_id}/{source_id}/"

        # Delete source record. Document.source_id is set to NULL by
        # the FK ON DELETE SET NULL constraint — documents survive.
        # Chunks survive via Document.chunks cascade (unchanged).
        SourceRepository.delete(db, source=source)
        logger.info("source deleted", source_id=source_id)

        # Best-effort MinIO prefix cleanup. If this fails, the objects become
        # orphans (cleaned by S3 lifecycle policy or a cron script).
        try:
            ObjectStorageService.delete_prefix(prefix=prefix)
        except Exception:
            logger.warning(
                "failed to clean up S3 objects after source delete",
                prefix=prefix,
                source_id=source_id,
            )

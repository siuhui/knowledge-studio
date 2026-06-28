import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.models.source import Source
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
        if source.status != "pending":
            raise ValidationError(
                code=ResponseCode.SOURCE_STATUS_INVALID,
                message=f"Cannot complete upload: source is already {source.status}",
            )
        source.config = config
        source.status = "active"
        source = SourceRepository.save(db, source=source)
        logger.info("source activated", source_id=source_id)
        return source

    @staticmethod
    def mark_error(*, source_id: str) -> None:
        """Mark a source as error. Creates its own DB session — safe for background tasks."""
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            source = db.get(Source, source_id)
            if source and source.status != "error":
                source.status = "error"
                db.commit()
                logger.info("source marked as error", source_id=source_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

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
        """Delete a source, its documents, and its MinIO objects.

        Deletes the DB record first (so the transaction can roll back if
        it fails), then does best-effort MinIO prefix cleanup. If MinIO
        cleanup fails, the objects become orphans cleaned by lifecycle
        policy — the safer failure mode than dangling DB references.

        Uses delete_prefix based on source_id — catches all objects
        uploaded for this source, including failed/partial uploads.
        """
        source = SourceService.get_by_id(db, source_id=source_id, user_id=user_id)

        prefix = f"uploads/{source.knowledge_base_id}/{source_id}/"

        # Delete DB record first: if this fails, the transaction rolls back
        # and MinIO is untouched — both stay consistent.
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

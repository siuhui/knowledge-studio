import structlog
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.core.security import validate_url
from app.models.source import Source
from app.models.status_enums import SourceStatus
from app.repositories.source import SourceRepository
from app.services.knowledge_base import KnowledgeBaseService
from app.services.object_storage import ObjectStorageService

logger = structlog.get_logger(__name__)

SUPPORTED_SOURCE_TYPES = {"upload", "url"}


class SourceService:
    """Source CRUD and config helpers.

    Does NOT know about ingestion — source creation and document ingestion
    are separate concerns, wired together by the API layer.
    """

    @staticmethod
    def create(
        db: Session,
        *,
        knowledge_base_id: str,
        user_id: str,
        type: str = "upload",
        config: dict[str, object] | None = None,
    ) -> Source:
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

        if type == "url":
            url = (source.config or {}).get("url")
            if not url or not isinstance(url, str):
                raise ValidationError(
                    code=ResponseCode.SOURCE_CONFIG_INVALID,
                    message="Source config must contain a 'url' string",
                )
            validate_url(url)
            source.config = {**source.config, "url": url}
            source.status = SourceStatus.ACTIVE

        source = SourceRepository.save(db, source=source)
        logger.info("source created", source_id=source.id, knowledge_base_id=knowledge_base_id)
        return source

    @staticmethod
    def validate_processable(source: Source) -> None:
        """Raise if the source status does not allow ingestion."""
        if source.status not in (SourceStatus.ACTIVE, SourceStatus.INVALID):
            raise ValidationError(
                code=ResponseCode.SOURCE_STATUS_INVALID,
                message=f"Cannot process source in '{source.status}' state",
            )

    @staticmethod
    def update_config(
        db: Session,
        *,
        source_id: str,
        config: dict[str, object],
    ) -> Source:
        """Merge additional fields into source config without changing status."""
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
        source.config = {**source.config, **config}
        SourceRepository.save(db, source=source)
        return source

    @staticmethod
    def activate(db: Session, *, source_id: str) -> Source:
        """Transition source from pending → active."""
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
        if source.status != SourceStatus.PENDING:
            raise ValidationError(
                code=ResponseCode.SOURCE_STATUS_INVALID,
                message=f"Cannot activate source: status is already {source.status}",
            )
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
    def mark_active(*, source_id: str) -> None:
        """Recover a source from invalid back to active (e.g. after retry succeeds).

        Creates its own DB session — safe for background tasks.
        """
        from app.database import SessionLocal

        with SessionLocal() as db:
            with db.begin():
                source = db.get(Source, source_id)
                if source and source.status == SourceStatus.INVALID:
                    source.status = SourceStatus.ACTIVE
                    logger.info("source recovered to active", source_id=source_id)

    @staticmethod
    def get_by_id(db: Session, *, source_id: str, user_id: str) -> Source:
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
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
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)
        offset = (page - 1) * page_size
        return SourceRepository.list_by_knowledge_base(
            db, knowledge_base_id=knowledge_base_id, offset=offset, limit=page_size
        )

    @staticmethod
    def delete(db: Session, *, source_id: str, user_id: str) -> None:
        source = SourceService.get_by_id(db, source_id=source_id, user_id=user_id)

        prefix = f"uploads/{source.knowledge_base_id}/{source_id}/"

        SourceRepository.delete(db, source=source)
        logger.info("source deleted", source_id=source_id)

        if source.type == "upload":
            try:
                ObjectStorageService.delete_prefix(prefix=prefix)
            except Exception:
                logger.warning(
                    "failed to clean up S3 objects after source delete",
                    prefix=prefix,
                    source_id=source_id,
                )

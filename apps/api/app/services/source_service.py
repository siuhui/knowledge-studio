import structlog
from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.core.errors import NotFoundError, ValidationError
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.knowledge_base_service import KnowledgeBaseService

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
        config: dict | None = None,
    ) -> Source:
        # Verify ownership
        KnowledgeBaseService.get_by_id(
            db, knowledge_base_id=knowledge_base_id, user_id=user_id
        )

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
    def get_by_id(db: Session, *, source_id: str) -> Source:
        source = SourceRepository.get_by_id(db, source_id=source_id)
        if not source:
            raise NotFoundError(
                code=ResponseCode.SOURCE_NOT_FOUND,
                message=f"Source {source_id} not found",
            )
        return source

    @staticmethod
    def list_by_knowledge_base(
        db: Session,
        *,
        knowledge_base_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Source], int]:
        offset = (page - 1) * page_size
        return SourceRepository.list_by_knowledge_base(
            db, knowledge_base_id=knowledge_base_id, offset=offset, limit=page_size
        )

    @staticmethod
    def delete(db: Session, *, source_id: str) -> None:
        source = SourceService.get_by_id(db, source_id=source_id)
        SourceRepository.delete(db, source=source)
        logger.info("source deleted", source_id=source_id)

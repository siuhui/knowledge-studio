import structlog
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.core.response_codes import ResponseCode
from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import KnowledgeBaseRepository

logger = structlog.get_logger(__name__)


class KnowledgeBaseService:
    @staticmethod
    def create(
        db: Session,
        *,
        user_id: str,
        name: str,
        description: str | None = None,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            user_id=user_id,
            name=name,
            description=description,
        )
        knowledge_base = KnowledgeBaseRepository.save(db, knowledge_base=knowledge_base)
        logger.info(
            "knowledge_base created",
            knowledge_base_id=knowledge_base.id,
            user_id=user_id,
        )
        return knowledge_base

    @staticmethod
    def get_by_id(db: Session, *, knowledge_base_id: str, user_id: str) -> KnowledgeBase:
        knowledge_base = KnowledgeBaseRepository.get_by_id(db, knowledge_base_id=knowledge_base_id)
        if not knowledge_base:
            raise NotFoundError(
                code=ResponseCode.KNOWLEDGE_BASE_NOT_FOUND,
                message=f"KnowledgeBase {knowledge_base_id} not found",
            )
        if knowledge_base.user_id != user_id:
            raise ForbiddenError(
                code=ResponseCode.KNOWLEDGE_BASE_ACCESS_DENIED,
                message="Access denied",
            )
        return knowledge_base

    @staticmethod
    def list_by_user(
        db: Session,
        *,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeBase], int]:
        offset = (page - 1) * page_size
        return KnowledgeBaseRepository.list_by_user(db, user_id=user_id, offset=offset, limit=page_size)

    @staticmethod
    def update(
        db: Session,
        *,
        knowledge_base_id: str,
        user_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)
        if name is not None:
            knowledge_base.name = name
        if description is not None:
            knowledge_base.description = description
        KnowledgeBaseRepository.save(db, knowledge_base=knowledge_base)
        logger.info("knowledge_base updated", knowledge_base_id=knowledge_base.id)
        return knowledge_base

    @staticmethod
    def delete(db: Session, *, knowledge_base_id: str, user_id: str) -> None:
        knowledge_base = KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=user_id)
        KnowledgeBaseRepository.delete(db, knowledge_base=knowledge_base)
        logger.info("knowledge_base deleted", knowledge_base_id=knowledge_base_id)

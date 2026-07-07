from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.models.status_enums import StudioTaskStatus
from app.models.studio_task import StudioTask
from app.repositories.studio_task import StudioTaskRepository
from app.schemas.studio import StudioTaskCreate
from app.services.knowledge_base import KnowledgeBaseService
from app.services.object_storage import ObjectStorageService

logger = structlog.get_logger(__name__)


class StudioService:
    """Studio task CRUD — lifecycle management only, no execution logic."""

    @staticmethod
    def create_task(db: Session, *, kb_id: str, user_id: str, payload: StudioTaskCreate) -> StudioTask:
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=kb_id, user_id=user_id)

        config = payload.config.model_dump()

        # [] = no documents selected → reject; null = all documents (default)
        doc_ids = config.get("document_ids")
        if doc_ids is not None and len(doc_ids) == 0:
            raise ValidationError(
                code=ResponseCode.VALIDATION_ERROR,
                message="document_ids must be null (all documents) or a non-empty list, not []",
            )

        task = StudioTask(
            knowledge_base_id=kb_id,
            user_id=user_id,
            task_type=payload.task_type,
            title=payload.title,
            config=config,
        )
        return StudioTaskRepository.save(db, task=task)

    @staticmethod
    def get_task(db: Session, *, task_id: str, kb_id: str, user_id: str) -> StudioTask:
        task = StudioTaskRepository.get_by_id(db, task_id=task_id)
        if task is None or task.knowledge_base_id != kb_id or task.user_id != user_id:
            raise NotFoundError(
                code=ResponseCode.STUDIO_TASK_NOT_FOUND,
                message=f"Studio task {task_id} not found",
            )
        return task

    @staticmethod
    def list_tasks(
        db: Session, *, kb_id: str, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[StudioTask], int]:
        KnowledgeBaseService.get_by_id(db, knowledge_base_id=kb_id, user_id=user_id)

        offset = (page - 1) * page_size
        tasks, total = StudioTaskRepository.list_by_kb(db, kb_id=kb_id, offset=offset, limit=page_size)
        return tasks, total

    @staticmethod
    def delete_task(db: Session, *, task_id: str, kb_id: str, user_id: str) -> None:
        task = StudioService.get_task(db, task_id=task_id, kb_id=kb_id, user_id=user_id)

        if task.output_s3_key:
            try:
                ObjectStorageService.delete(key=task.output_s3_key)
            except AppError:
                logger.warning("failed to delete report from storage", s3_key=task.output_s3_key)

        StudioTaskRepository.delete(db, task=task)

    @staticmethod
    def get_download_url(task: StudioTask) -> str:
        if task.status != StudioTaskStatus.COMPLETED:
            raise ValidationError(
                code=ResponseCode.STUDIO_TASK_NOT_COMPLETED,
                message=f"Task is not completed (status: {task.status})",
            )
        if task.output_s3_key is None:
            raise NotFoundError(
                code=ResponseCode.STUDIO_TASK_NOT_FOUND,
                message="Report file not available",
            )
        return ObjectStorageService.generate_presigned_get(key=task.output_s3_key)

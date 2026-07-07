from __future__ import annotations

from datetime import UTC, datetime

import structlog

from app.core.telemetry import observe, trace_context, update_current_span
from app.database import SessionLocal
from app.models.status_enums import StudioTaskStatus
from app.models.studio_task import StudioTask
from app.repositories.studio_task import StudioTaskRepository
from app.services.object_storage import ObjectStorageService
from app.services.studio.workflows.report import ReportWorkflow

logger = structlog.get_logger(__name__)


@observe(name="studio.task", capture_input=False, capture_output=False)
def execute_studio_task(task_id: str) -> None:
    """Background task entry point. Creates its own DB session and runs the pipeline."""
    update_current_span(input={"task_id": task_id})

    db = SessionLocal()
    try:
        task: StudioTask | None = StudioTaskRepository.get_by_id(db, task_id=task_id)
        if task is None:
            logger.error("studio task not found for execution", task_id=task_id)
            update_current_span(level="ERROR", status_message="Task not found")
            return

        with trace_context(user_id=task.user_id, tags=["studio", task.task_type]):
            _task = task  # capture narrowed type for closure
            _task.status = StudioTaskStatus.RUNNING
            _task.started_at = datetime.now(UTC)
            StudioTaskRepository.save(db, task=_task)
            db.commit()

            def update_progress(progress: float, message: str) -> None:
                _task.progress = progress
                _task.status_message = message
                StudioTaskRepository.save(db, task=_task)
                db.commit()

            workflow = ReportWorkflow(update_progress)
            run_config = dict(_task.config)
            run_config["title"] = _task.title
            markdown, chapter_count = workflow.execute(db, config=run_config, kb_id=_task.knowledge_base_id)

            s3_key = f"studio/{_task.knowledge_base_id}/{_task.id}/report.md"
            update_progress(0.95, "Storing report...")
            ObjectStorageService.put(key=s3_key, body=markdown.encode("utf-8"), content_type="text/markdown")

            _task.status = StudioTaskStatus.COMPLETED
            _task.progress = 1.0
            _task.status_message = None
            _task.output_s3_key = s3_key
            _task.output_metadata = {"char_count": len(markdown), "chapter_count": chapter_count}
            _task.completed_at = datetime.now(UTC)
            StudioTaskRepository.save(db, task=_task)
            db.commit()

            update_current_span(
                output={
                    "status": "completed",
                    "s3_key": s3_key,
                    "char_count": len(markdown),
                    "chapter_count": chapter_count,
                }
            )
            logger.info(
                "studio task completed",
                task_id=task_id,
                char_count=len(markdown),
                chapter_count=chapter_count,
            )

    except Exception as exc:
        db.rollback()
        update_current_span(level="ERROR", status_message=str(exc))
        logger.error("studio task failed", task_id=task_id, error=str(exc), exc_info=True)
        try:
            task = StudioTaskRepository.get_by_id(db, task_id=task_id)
            if task is not None:
                task.status = StudioTaskStatus.FAILED
                task.error_message = str(exc)
                StudioTaskRepository.save(db, task=task)
                db.commit()
        except Exception:
            logger.error("failed to mark task as failed", task_id=task_id, exc_info=True)
    finally:
        db.close()

from sqlalchemy.orm import Session

from app.models.studio_task import StudioTask


class StudioTaskRepository:
    @staticmethod
    def get_by_id(db: Session, *, task_id: str) -> StudioTask | None:
        return db.get(StudioTask, task_id)

    @staticmethod
    def list_by_kb(db: Session, *, kb_id: str, offset: int = 0, limit: int = 20) -> tuple[list[StudioTask], int]:
        query = db.query(StudioTask).filter(StudioTask.knowledge_base_id == kb_id)
        total = query.count()
        items = query.order_by(StudioTask.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def save(db: Session, *, task: StudioTask) -> StudioTask:
        db.add(task)
        db.flush()
        return task

    @staticmethod
    def delete(db: Session, *, task: StudioTask) -> None:
        db.delete(task)
        db.flush()

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeSource

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


def _trace_id() -> str:
    return str(uuid.uuid4())


@router.post("")
def create_source(payload: dict, db: Session = Depends(get_db)) -> dict:
    source = KnowledgeSource(
        name=payload.get("name", "default-source"),
        source_type=payload.get("source_type", "local"),
        sync_mode=payload.get("sync_mode", "scheduled"),
        status=payload.get("status", "active"),
        config_json=payload.get("config_json"),
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    return {
        "code": "OK",
        "message": "created",
        "data": {
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "status": source.status,
        },
        "trace_id": _trace_id(),
    }


@router.get("")
def list_sources(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(KnowledgeSource)).all()
    return {
        "code": "OK",
        "message": "success",
        "data": {
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "source_type": row.source_type,
                    "sync_mode": row.sync_mode,
                    "status": row.status,
                }
                for row in rows
            ]
        },
        "trace_id": _trace_id(),
    }

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeSource
from ..schemas import ApiResponse, SourceCreateRequest, SourceItem, SourceListPayload

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


def _trace_id() -> str:
    return str(uuid.uuid4())


@router.post("", response_model=ApiResponse[SourceItem])
def create_source(payload: SourceCreateRequest, db: Session = Depends(get_db)) -> ApiResponse[SourceItem]:
    source = KnowledgeSource(
        name=payload.name,
        source_type=payload.source_type,
        sync_mode=payload.sync_mode,
        status=payload.status,
        config_json=payload.config_json,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    return ApiResponse[SourceItem](
        message="created",
        data=SourceItem(
            id=source.id,
            name=source.name,
            source_type=source.source_type,
            sync_mode=source.sync_mode,
            status=source.status,
        ),
        trace_id=_trace_id(),
    )


@router.get("", response_model=ApiResponse[SourceListPayload])
def list_sources(db: Session = Depends(get_db)) -> ApiResponse[SourceListPayload]:
    rows = db.scalars(select(KnowledgeSource)).all()
    items = [
        SourceItem(
            id=row.id,
            name=row.name,
            source_type=row.source_type,
            sync_mode=row.sync_mode,
            status=row.status,
        )
        for row in rows
    ]
    return ApiResponse[SourceListPayload](
        message="success",
        data=SourceListPayload(items=items),
        trace_id=_trace_id(),
    )

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.source import SourceCreate, SourceItem
from app.services.source_service import SourceService

router = APIRouter(tags=["sources"])


@router.post(
    "/api/v1/knowledge-bases/{knowledge_base_id}/sources",
    response_model=ApiResponse[SourceItem],
)
def create_source(
    knowledge_base_id: str,
    payload: SourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[SourceItem]:
    source = SourceService.create(
        db,
        knowledge_base_id=knowledge_base_id,
        user_id=current_user.id,
        type=payload.type,
        config=payload.config,
    )
    return ApiResponse[SourceItem](
        code="OK",
        message="Source created",
        data=SourceItem.model_validate(source),
    )


@router.get(
    "/api/v1/knowledge-bases/{knowledge_base_id}/sources",
    response_model=PaginatedResponse[SourceItem],
)
def list_sources(
    knowledge_base_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[SourceItem]:
    items, total = SourceService.list_by_knowledge_base(
        db, knowledge_base_id=knowledge_base_id, page=page, page_size=page_size
    )
    return PaginatedResponse[SourceItem](
        code="OK",
        message="success",
        data=[SourceItem.model_validate(item) for item in items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.delete(
    "/api/v1/sources/{source_id}",
    response_model=ApiResponse[None],
)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    SourceService.delete(db, source_id=source_id)
    return ApiResponse[None](code="OK", message="Source deleted", data=None)

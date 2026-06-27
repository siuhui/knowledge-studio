from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
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
        code=ResponseCode.OK,
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
        code=ResponseCode.OK,
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
    return ApiResponse[None](code=ResponseCode.OK, message="Source deleted", data=None)


@router.get(
    "/api/v1/sources/{source_id}/documents",
    response_model=PaginatedResponse[dict],
)
def list_documents(
    source_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[dict]:
    """List documents belonging to a source."""
    source = SourceService.get_by_id(db, source_id=source_id)
    items, total = DocumentRepository.list_by_source(
        db,
        source_id=source.id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse[dict](
        code=ResponseCode.OK,
        message="success",
        data=[
            {
                "id": item.id,
                "source_id": item.source_id,
                "title": item.title,
                "source_format": item.source_format,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )

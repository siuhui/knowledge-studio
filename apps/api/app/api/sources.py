import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.response_codes import ResponseCode
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.source import SourceCreate, SourceItem
from app.services.index_pipeline import run_index_pipeline
from app.services.object_storage import ObjectStorageService
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

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
    """Create a source in pending status. Upload and indexing happen separately."""
    source = SourceService.create(
        db,
        knowledge_base_id=knowledge_base_id,
        user_id=current_user.id,
        type=payload.type,
        config=payload.config,
    )

    logger.info("source created (pending)", source_id=source.id, kb_id=knowledge_base_id)

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
        db, knowledge_base_id=knowledge_base_id, user_id=current_user.id, page=page, page_size=page_size
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
    SourceService.delete(db, source_id=source_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="Source deleted", data=None)


@router.get(
    "/api/v1/sources/{source_id}/documents",
    response_model=PaginatedResponse[dict[str, object]],
)
def list_documents(
    source_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[dict[str, object]]:
    """List documents belonging to a source."""
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)
    items, total = DocumentRepository.list_by_source(
        db,
        source_id=source.id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse[dict[str, object]](
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


@router.post(
    "/api/v1/sources/{source_id}/extract",
    response_model=ApiResponse[dict[str, object]],
)
def extract_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, object]]:
    """Re-extract a source: download from MinIO and re-run indexing pipeline.

    Only active or error sources can be re-extracted. If the S3 object
    is missing, the source is marked as error.
    """
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)

    # Guard: source must be active or error to re-extract
    if source.status not in ("active", "error"):
        raise ValidationError(
            code=ResponseCode.SOURCE_STATUS_INVALID,
            message=f"Cannot re-extract source in '{source.status}' state",
        )

    s3_key = (source.config or {}).get("s3_key")
    if not s3_key or not isinstance(s3_key, str):
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message="Source has no linked file to re-extract",
        )

    # Verify object still exists in storage
    try:
        ObjectStorageService.head_object(key=s3_key)
    except NotFoundError:
        source.status = "error"
        db.flush()
        logger.warning(
            "source object not found, marked as error",
            source_id=source_id,
            s3_key=s3_key,
        )
        raise ValidationError(
            code=ResponseCode.UPLOAD_OBJECT_NOT_FOUND,
            message="Source file no longer exists in storage. Source marked as error.",
        )

    original_name = source.config.get("original_name", "unknown")

    background_tasks.add_task(
        run_index_pipeline,
        source_id=source_id,
        s3_key=s3_key,
        filename=str(original_name),
    )

    logger.info("re-extract scheduled", source_id=source_id)

    return ApiResponse[dict[str, object]](
        code=ResponseCode.OK,
        message="Re-extraction started",
        data={"source_id": source_id},
    )

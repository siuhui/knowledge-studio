import structlog
from fastapi import APIRouter, BackgroundTasks, Query

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.document import DocumentItem
from app.schemas.source import SourceCreate, SourceItem
from app.services.document import DocumentService
from app.services.ingestion import IngestionService
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["sources"])


@router.post(
    "/api/v1/knowledge-bases/{knowledge_base_id}/sources",
    response_model=ApiResponse[SourceItem],
)
def create_source(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    payload: SourceCreate,
) -> ApiResponse[SourceItem]:
    """Create a source. URL sources are activated immediately; upload sources
    stay pending until /uploads/complete validates the S3 object."""
    source = SourceService.create(
        db,
        knowledge_base_id=knowledge_base_id,
        user_id=current_user.id,
        type=payload.type,
        config=payload.config,
    )

    logger.info(
        "source_created",
        source_id=source.id,
        knowledge_base_id=knowledge_base_id,
        status=source.status,
    )

    return ApiResponse[SourceItem](
        code=ResponseCode.OK,
        message="Source created",
        data=SourceItem.model_validate(source),
    )


@router.post(
    "/api/v1/sources/{source_id}/process",
    response_model=ApiResponse[dict[str, object]],
)
def process_source(
    db: DbSession,
    current_user: CurrentUser,
    source_id: str,
    background_tasks: BackgroundTasks,
) -> ApiResponse[dict[str, object]]:
    """Trigger ingestion for an active (or invalid, for retry) source."""
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)
    SourceService.validate_processable(source)

    IngestionService.dispatch(source, background_tasks)

    return ApiResponse[dict[str, object]](
        code=ResponseCode.OK,
        message="Processing started",
        data={"source_id": source_id},
    )


@router.get(
    "/api/v1/knowledge-bases/{knowledge_base_id}/sources",
    response_model=PaginatedResponse[SourceItem],
)
def list_sources(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
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
    db: DbSession,
    current_user: CurrentUser,
    source_id: str,
) -> ApiResponse[None]:
    SourceService.delete(db, source_id=source_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="Source deleted", data=None)


@router.get(
    "/api/v1/sources/{source_id}/documents",
    response_model=PaginatedResponse[dict[str, object]],
)
def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    source_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse[dict[str, object]]:
    items, total = DocumentService.list_by_source(
        db,
        source_id=source_id,
        user_id=current_user.id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse[dict[str, object]](
        code=ResponseCode.OK,
        message="success",
        data=[DocumentItem.model_validate(item).model_dump(mode="json") for item in items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )

from fastapi import APIRouter, Query

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseItem, KnowledgeBaseUpdate
from app.services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=PaginatedResponse[KnowledgeBaseItem])
def list_knowledge_bases(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[KnowledgeBaseItem]:
    items, total = KnowledgeBaseService.list_by_user(db, user_id=current_user.id, page=page, page_size=page_size)
    return PaginatedResponse[KnowledgeBaseItem](
        code=ResponseCode.OK,
        message="success",
        data=[KnowledgeBaseItem.model_validate(item) for item in items],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post("", response_model=ApiResponse[KnowledgeBaseItem])
def create_knowledge_base(
    db: DbSession,
    current_user: CurrentUser,
    payload: KnowledgeBaseCreate,
) -> ApiResponse[KnowledgeBaseItem]:
    knowledge_base = KnowledgeBaseService.create(
        db, user_id=current_user.id, name=payload.name, description=payload.description
    )
    return ApiResponse[KnowledgeBaseItem](
        code=ResponseCode.OK,
        message="KnowledgeBase created",
        data=KnowledgeBaseItem.model_validate(knowledge_base),
    )


@router.get("/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBaseItem])
def get_knowledge_base(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
) -> ApiResponse[KnowledgeBaseItem]:
    knowledge_base = KnowledgeBaseService.get_by_id(db, knowledge_base_id=knowledge_base_id, user_id=current_user.id)
    return ApiResponse[KnowledgeBaseItem](
        code=ResponseCode.OK,
        message="success",
        data=KnowledgeBaseItem.model_validate(knowledge_base),
    )


@router.patch("/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBaseItem])
def update_knowledge_base(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    payload: KnowledgeBaseUpdate,
) -> ApiResponse[KnowledgeBaseItem]:
    knowledge_base = KnowledgeBaseService.update(
        db,
        knowledge_base_id=knowledge_base_id,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    return ApiResponse[KnowledgeBaseItem](
        code=ResponseCode.OK,
        message="KnowledgeBase updated",
        data=KnowledgeBaseItem.model_validate(knowledge_base),
    )


@router.delete("/{knowledge_base_id}", response_model=ApiResponse[None])
def delete_knowledge_base(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
) -> ApiResponse[None]:
    KnowledgeBaseService.delete(db, knowledge_base_id=knowledge_base_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="KnowledgeBase deleted", data=None)

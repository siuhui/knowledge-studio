from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import (
    ApiResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseMemberItem,
    KnowledgeBaseMemberListPayload,
    KnowledgeBaseMemberUpsertRequest,
    PermissionCheckPayload,
)
from ..services.access_control import can_access, resolve_kb_role
from ..services.knowledge_bases_service import (
    create_knowledge_base,
    get_knowledge_base_by_id,
    list_knowledge_base_members,
    upsert_knowledge_base_member,
)

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=ApiResponse[KnowledgeBaseItem])
def create_knowledge_base_api(
    payload: KnowledgeBaseCreateRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[KnowledgeBaseItem]:
    kb = create_knowledge_base(
        db,
        name=payload.name,
        owner_team_id=payload.owner_team_id,
        owner_user_id=payload.owner_user_id,
        status=payload.status,
        trace_id=get_trace_id(request),
    )
    return ApiResponse[KnowledgeBaseItem](
        message="created",
        data=KnowledgeBaseItem(id=kb.id, name=kb.name, owner_team_id=kb.owner_team_id, status=kb.status.value),
        trace_id=get_trace_id(request),
    )


@router.post("/{kb_id}/members", response_model=ApiResponse[KnowledgeBaseMemberItem])
def upsert_knowledge_base_member_api(
    kb_id: str,
    payload: KnowledgeBaseMemberUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[KnowledgeBaseMemberItem]:
    row = upsert_knowledge_base_member(
        db,
        knowledge_base_id=kb_id,
        operator_user_id=payload.operator_user_id,
        user_id=payload.user_id,
        role=payload.role,
        trace_id=get_trace_id(request),
    )
    return ApiResponse[KnowledgeBaseMemberItem](
        message="upserted",
        data=KnowledgeBaseMemberItem(user_id=row.user_id, knowledge_base_id=row.knowledge_base_id, role=row.role.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{kb_id}/members", response_model=ApiResponse[KnowledgeBaseMemberListPayload])
def list_knowledge_base_members_api(
    kb_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[KnowledgeBaseMemberListPayload]:
    rows = list_knowledge_base_members(db, knowledge_base_id=kb_id)
    items = [
        KnowledgeBaseMemberItem(user_id=row.user_id, knowledge_base_id=row.knowledge_base_id, role=row.role.value)
        for row in rows
    ]
    return ApiResponse[KnowledgeBaseMemberListPayload](
        message="success",
        data=KnowledgeBaseMemberListPayload(items=items),
        trace_id=get_trace_id(request),
    )


@router.get("/{kb_id}/permissions/{user_id}", response_model=ApiResponse[PermissionCheckPayload])
def check_permission(
    kb_id: str,
    user_id: str,
    request: Request,
    action: str = Query(..., pattern="^(read|write|delete)$"),
    db: Session = Depends(get_db),
) -> ApiResponse[PermissionCheckPayload]:
    _ = get_knowledge_base_by_id(db, knowledge_base_id=kb_id)
    role, source = resolve_kb_role(db, user_id=user_id, knowledge_base_id=kb_id)
    allowed = can_access(action, role)
    return ApiResponse[PermissionCheckPayload](
        message="success",
        data=PermissionCheckPayload(
            user_id=user_id,
            knowledge_base_id=kb_id,
            action=action,
            role=role,
            allowed=allowed,
            source=source,
        ),
        trace_id=get_trace_id(request),
    )

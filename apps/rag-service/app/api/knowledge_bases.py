import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..models import (
    KnowledgeBase,
    KnowledgeBaseMembership,
    KnowledgeBaseRole,
    KnowledgeBaseStatus,
    Team,
    TeamMembership,
    User,
)
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

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=ApiResponse[KnowledgeBaseItem])
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[KnowledgeBaseItem]:
    team = db.get(Team, payload.owner_team_id)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEAM_NOT_FOUND",
                "message": f"owner_team_id {payload.owner_team_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    owner = db.get(User, payload.owner_user_id)
    if owner is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "USER_NOT_FOUND",
                "message": f"owner_user_id {payload.owner_user_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    owner_team_membership = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == payload.owner_team_id, TeamMembership.user_id == payload.owner_user_id
        )
    )
    if owner_team_membership is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OWNER_NOT_IN_TEAM",
                "message": "owner_user_id must belong to owner_team_id",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    kb = KnowledgeBase(
        id=str(uuid.uuid4()),
        name=payload.name,
        owner_team_id=payload.owner_team_id,
        status=KnowledgeBaseStatus(payload.status),
    )
    db.add(kb)
    db.flush()

    owner_binding = KnowledgeBaseMembership(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb.id,
        user_id=payload.owner_user_id,
        role=KnowledgeBaseRole.owner,
    )
    db.add(owner_binding)
    db.commit()
    db.refresh(kb)

    return ApiResponse[KnowledgeBaseItem](
        message="created",
        data=KnowledgeBaseItem(id=kb.id, name=kb.name, owner_team_id=kb.owner_team_id, status=kb.status.value),
        trace_id=get_trace_id(request),
    )


@router.post("/{kb_id}/members", response_model=ApiResponse[KnowledgeBaseMemberItem])
def upsert_knowledge_base_member(
    kb_id: str,
    payload: KnowledgeBaseMemberUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[KnowledgeBaseMemberItem]:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "KNOWLEDGE_BASE_NOT_FOUND",
                "message": f"knowledge_base_id {kb_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "USER_NOT_FOUND",
                "message": f"user_id {payload.user_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    row = db.scalar(
        select(KnowledgeBaseMembership).where(
            KnowledgeBaseMembership.knowledge_base_id == kb_id,
            KnowledgeBaseMembership.user_id == payload.user_id,
        )
    )
    if row is None:
        row = KnowledgeBaseMembership(
            id=str(uuid.uuid4()),
            knowledge_base_id=kb_id,
            user_id=payload.user_id,
            role=KnowledgeBaseRole(payload.role),
        )
        db.add(row)
    else:
        row.role = KnowledgeBaseRole(payload.role)

    db.commit()
    db.refresh(row)

    return ApiResponse[KnowledgeBaseMemberItem](
        message="upserted",
        data=KnowledgeBaseMemberItem(user_id=row.user_id, knowledge_base_id=row.knowledge_base_id, role=row.role.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{kb_id}/members", response_model=ApiResponse[KnowledgeBaseMemberListPayload])
def list_knowledge_base_members(
    kb_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[KnowledgeBaseMemberListPayload]:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "KNOWLEDGE_BASE_NOT_FOUND",
                "message": f"knowledge_base_id {kb_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    rows = db.scalars(select(KnowledgeBaseMembership).where(KnowledgeBaseMembership.knowledge_base_id == kb_id)).all()
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
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "KNOWLEDGE_BASE_NOT_FOUND",
                "message": f"knowledge_base_id {kb_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

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

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import error_codes
from ..core.errors import BadRequestError, NotFoundError, PermissionDeniedError
from ..core.uow import transactional
from ..models import (
    KnowledgeBase,
    KnowledgeBaseMembership,
    KnowledgeBaseRole,
    KnowledgeBaseStatus,
    Team,
    TeamMembership,
    User,
)
from .access_control import can_access, resolve_kb_role
from .audit import write_audit_log


def get_knowledge_base_by_id(db: Session, *, knowledge_base_id: str) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, knowledge_base_id)
    if kb is None:
        raise NotFoundError(
            code=error_codes.KNOWLEDGE_BASE_NOT_FOUND,
            message=f"knowledge_base_id {knowledge_base_id} not found",
        )
    return kb


def create_knowledge_base(
    db: Session,
    *,
    name: str,
    owner_team_id: str,
    owner_user_id: str,
    status: str,
    trace_id: str,
) -> KnowledgeBase:
    team = db.get(Team, owner_team_id)
    if team is None:
        raise NotFoundError(code=error_codes.TEAM_NOT_FOUND, message=f"owner_team_id {owner_team_id} not found")

    owner = db.get(User, owner_user_id)
    if owner is None:
        raise NotFoundError(code=error_codes.USER_NOT_FOUND, message=f"owner_user_id {owner_user_id} not found")

    owner_team_membership = db.scalar(
        select(TeamMembership).where(TeamMembership.team_id == owner_team_id, TeamMembership.user_id == owner_user_id)
    )
    if owner_team_membership is None:
        raise BadRequestError(
            code=error_codes.OWNER_NOT_IN_TEAM,
            message="owner_user_id must belong to owner_team_id",
        )

    kb = KnowledgeBase(
        id=str(uuid.uuid4()),
        name=name,
        owner_team_id=owner_team_id,
        status=KnowledgeBaseStatus(status),
    )
    owner_binding = KnowledgeBaseMembership(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb.id,
        user_id=owner_user_id,
        role=KnowledgeBaseRole.owner,
    )
    with transactional(db):
        db.add(kb)
        db.add(owner_binding)
        write_audit_log(
            db,
            actor_id=owner_user_id,
            action="KNOWLEDGE_BASE_CREATE",
            resource_type="knowledge_base",
            resource_id=kb.id,
            trace_id=trace_id,
        )
        write_audit_log(
            db,
            actor_id=owner_user_id,
            action="KNOWLEDGE_BASE_MEMBER_UPSERT",
            resource_type="knowledge_base_membership",
            resource_id=owner_binding.id,
            trace_id=trace_id,
        )
    return kb


def upsert_knowledge_base_member(
    db: Session,
    *,
    knowledge_base_id: str,
    operator_user_id: str,
    user_id: str,
    role: str,
    trace_id: str,
) -> KnowledgeBaseMembership:
    _ = get_knowledge_base_by_id(db, knowledge_base_id=knowledge_base_id)

    operator_role, _ = resolve_kb_role(db, user_id=operator_user_id, knowledge_base_id=knowledge_base_id)
    if not can_access("delete", operator_role):
        raise PermissionDeniedError(message="only owner can manage knowledge base members")

    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(code=error_codes.USER_NOT_FOUND, message=f"user_id {user_id} not found")

    row = db.scalar(
        select(KnowledgeBaseMembership).where(
            KnowledgeBaseMembership.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseMembership.user_id == user_id,
        )
    )
    if row is None:
        row = KnowledgeBaseMembership(
            id=str(uuid.uuid4()),
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            role=KnowledgeBaseRole(role),
        )
    else:
        row.role = KnowledgeBaseRole(role)

    with transactional(db):
        db.add(row)
        write_audit_log(
            db,
            actor_id=operator_user_id,
            action="KNOWLEDGE_BASE_MEMBER_UPSERT",
            resource_type="knowledge_base_membership",
            resource_id=row.id,
            trace_id=trace_id,
        )
    return row


def list_knowledge_base_members(db: Session, *, knowledge_base_id: str) -> list[KnowledgeBaseMembership]:
    _ = get_knowledge_base_by_id(db, knowledge_base_id=knowledge_base_id)
    return db.scalars(
        select(KnowledgeBaseMembership).where(KnowledgeBaseMembership.knowledge_base_id == knowledge_base_id)
    ).all()

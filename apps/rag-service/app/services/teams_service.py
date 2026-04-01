import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import error_codes
from ..core.errors import ConflictError, NotFoundError, PermissionDeniedError
from ..core.uow import transactional
from ..models import Team, TeamMembership, TeamRole, TeamStatus, User
from .audit import write_audit_log


def create_team(
    db: Session,
    *,
    name: str,
    creator_user_id: str,
    status: str,
    trace_id: str,
) -> Team:
    creator = db.get(User, creator_user_id)
    if creator is None:
        raise NotFoundError(code=error_codes.USER_NOT_FOUND, message=f"creator_user_id {creator_user_id} not found")

    exists = db.scalar(select(Team).where(Team.name == name))
    if exists is not None:
        raise ConflictError(code=error_codes.TEAM_NAME_EXISTS, message=f"team name {name} already exists")

    team = Team(id=str(uuid.uuid4()), name=name, status=TeamStatus(status))
    admin_membership = TeamMembership(
        id=str(uuid.uuid4()),
        user_id=creator_user_id,
        team_id=team.id,
        role=TeamRole.team_admin,
    )
    with transactional(db):
        db.add(team)
        db.add(admin_membership)
        write_audit_log(
            db,
            actor_id=creator_user_id,
            action="TEAM_CREATE",
            resource_type="team",
            resource_id=team.id,
            trace_id=trace_id,
        )
        write_audit_log(
            db,
            actor_id=creator_user_id,
            action="TEAM_MEMBER_UPSERT",
            resource_type="team_membership",
            resource_id=admin_membership.id,
            trace_id=trace_id,
        )
    return team


def upsert_team_member(
    db: Session,
    *,
    team_id: str,
    operator_user_id: str,
    user_id: str,
    role: str,
    trace_id: str,
) -> TeamMembership:
    team = db.get(Team, team_id)
    if team is None:
        raise NotFoundError(code=error_codes.TEAM_NOT_FOUND, message=f"team_id {team_id} not found")

    operator = db.scalar(select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == operator_user_id))
    if operator is None or operator.role != TeamRole.team_admin:
        raise PermissionDeniedError(message="only team_admin can manage team members")

    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(code=error_codes.USER_NOT_FOUND, message=f"user_id {user_id} not found")

    membership = db.scalar(select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id))
    if membership is None:
        membership = TeamMembership(
            id=str(uuid.uuid4()),
            user_id=user_id,
            team_id=team_id,
            role=TeamRole(role),
        )
    else:
        membership.role = TeamRole(role)

    with transactional(db):
        db.add(membership)
        write_audit_log(
            db,
            actor_id=operator_user_id,
            action="TEAM_MEMBER_UPSERT",
            resource_type="team_membership",
            resource_id=membership.id,
            trace_id=trace_id,
        )
    return membership


def list_team_members(db: Session, *, team_id: str) -> list[TeamMembership]:
    team = db.get(Team, team_id)
    if team is None:
        raise NotFoundError(code=error_codes.TEAM_NOT_FOUND, message=f"team_id {team_id} not found")
    return db.scalars(select(TeamMembership).where(TeamMembership.team_id == team_id)).all()

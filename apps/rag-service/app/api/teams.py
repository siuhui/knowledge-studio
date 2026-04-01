import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..models import Team, TeamMembership, TeamRole, TeamStatus, User
from ..schemas import ApiResponse, TeamCreateRequest, TeamItem, TeamMemberItem, TeamMemberListPayload, TeamMemberUpsertRequest

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=ApiResponse[TeamItem])
def create_team(payload: TeamCreateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TeamItem]:
    creator = db.get(User, payload.creator_user_id)
    if creator is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "USER_NOT_FOUND",
                "message": f"creator_user_id {payload.creator_user_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    exists = db.scalar(select(Team).where(Team.name == payload.name))
    if exists is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TEAM_NAME_EXISTS",
                "message": f"team name {payload.name} already exists",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    team = Team(id=str(uuid.uuid4()), name=payload.name, status=TeamStatus(payload.status))
    db.add(team)
    db.flush()

    admin_membership = TeamMembership(
        id=str(uuid.uuid4()),
        user_id=payload.creator_user_id,
        team_id=team.id,
        role=TeamRole.team_admin,
    )
    db.add(admin_membership)
    db.commit()
    db.refresh(team)

    return ApiResponse[TeamItem](
        message="created",
        data=TeamItem(id=team.id, name=team.name, status=team.status.value),
        trace_id=get_trace_id(request),
    )


@router.post("/{team_id}/members", response_model=ApiResponse[TeamMemberItem])
def upsert_team_member(
    team_id: str, payload: TeamMemberUpsertRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[TeamMemberItem]:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEAM_NOT_FOUND",
                "message": f"team_id {team_id} not found",
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

    membership = db.scalar(
        select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == payload.user_id)
    )
    if membership is None:
        membership = TeamMembership(
            id=str(uuid.uuid4()),
            user_id=payload.user_id,
            team_id=team_id,
            role=TeamRole(payload.role),
        )
        db.add(membership)
    else:
        membership.role = TeamRole(payload.role)

    db.commit()
    db.refresh(membership)

    return ApiResponse[TeamMemberItem](
        message="upserted",
        data=TeamMemberItem(user_id=membership.user_id, team_id=membership.team_id, role=membership.role.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{team_id}/members", response_model=ApiResponse[TeamMemberListPayload])
def list_team_members(team_id: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TeamMemberListPayload]:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TEAM_NOT_FOUND",
                "message": f"team_id {team_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    rows = db.scalars(select(TeamMembership).where(TeamMembership.team_id == team_id)).all()
    items = [TeamMemberItem(user_id=row.user_id, team_id=row.team_id, role=row.role.value) for row in rows]
    return ApiResponse[TeamMemberListPayload](
        message="success",
        data=TeamMemberListPayload(items=items),
        trace_id=get_trace_id(request),
    )

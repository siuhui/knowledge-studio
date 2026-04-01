from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import ApiResponse, TeamCreateRequest, TeamItem, TeamMemberItem, TeamMemberListPayload, TeamMemberUpsertRequest
from ..services.teams_service import create_team, list_team_members, upsert_team_member

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=ApiResponse[TeamItem])
def create_team_api(payload: TeamCreateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TeamItem]:
    team = create_team(
        db,
        name=payload.name,
        creator_user_id=payload.creator_user_id,
        status=payload.status,
        trace_id=get_trace_id(request),
    )
    return ApiResponse[TeamItem](
        message="created",
        data=TeamItem(id=team.id, name=team.name, status=team.status.value),
        trace_id=get_trace_id(request),
    )


@router.post("/{team_id}/members", response_model=ApiResponse[TeamMemberItem])
def upsert_team_member_api(
    team_id: str, payload: TeamMemberUpsertRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[TeamMemberItem]:
    membership = upsert_team_member(
        db,
        team_id=team_id,
        operator_user_id=payload.operator_user_id,
        user_id=payload.user_id,
        role=payload.role,
        trace_id=get_trace_id(request),
    )
    return ApiResponse[TeamMemberItem](
        message="upserted",
        data=TeamMemberItem(user_id=membership.user_id, team_id=membership.team_id, role=membership.role.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{team_id}/members", response_model=ApiResponse[TeamMemberListPayload])
def list_team_members_api(
    team_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[TeamMemberListPayload]:
    rows = list_team_members(db, team_id=team_id)
    items = [TeamMemberItem(user_id=row.user_id, team_id=row.team_id, role=row.role.value) for row in rows]
    return ApiResponse[TeamMemberListPayload](
        message="success",
        data=TeamMemberListPayload(items=items),
        trace_id=get_trace_id(request),
    )

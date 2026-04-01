from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import ApiResponse, UserCreateRequest, UserItem
from ..services.users_service import create_user, get_user_by_id

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=ApiResponse[UserItem])
def create_user_api(payload: UserCreateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[UserItem]:
    user = create_user(db, email=payload.email, display_name=payload.display_name, status=payload.status)
    return ApiResponse[UserItem](
        message="created",
        data=UserItem(id=user.id, email=user.email, display_name=user.display_name, status=user.status.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{user_id}", response_model=ApiResponse[UserItem])
def get_user(user_id: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[UserItem]:
    user = get_user_by_id(db, user_id=user_id)
    return ApiResponse[UserItem](
        message="success",
        data=UserItem(id=user.id, email=user.email, display_name=user.display_name, status=user.status.value),
        trace_id=get_trace_id(request),
    )

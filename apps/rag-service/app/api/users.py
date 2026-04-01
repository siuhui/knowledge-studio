import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..models import User, UserStatus
from ..schemas import ApiResponse, UserCreateRequest, UserItem

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=ApiResponse[UserItem])
def create_user(payload: UserCreateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[UserItem]:
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "USER_EMAIL_EXISTS",
                "message": f"email {payload.email} already exists",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        display_name=payload.display_name,
        status=UserStatus(payload.status),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return ApiResponse[UserItem](
        message="created",
        data=UserItem(id=user.id, email=user.email, display_name=user.display_name, status=user.status.value),
        trace_id=get_trace_id(request),
    )


@router.get("/{user_id}", response_model=ApiResponse[UserItem])
def get_user(user_id: str, request: Request, db: Session = Depends(get_db)) -> ApiResponse[UserItem]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "USER_NOT_FOUND",
                "message": f"user_id {user_id} not found",
                "data": None,
                "trace_id": get_trace_id(request),
            },
        )

    return ApiResponse[UserItem](
        message="success",
        data=UserItem(id=user.id, email=user.email, display_name=user.display_name, status=user.status.value),
        trace_id=get_trace_id(request),
    )

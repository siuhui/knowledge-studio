import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import error_codes
from ..core.errors import ConflictError, NotFoundError
from ..core.uow import transactional
from ..models import User, UserStatus


def create_user(db: Session, *, email: str, display_name: str, status: str) -> User:
    exists = db.scalar(select(User).where(User.email == email))
    if exists is not None:
        raise ConflictError(code=error_codes.USER_EMAIL_EXISTS, message=f"email {email} already exists")

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=display_name,
        status=UserStatus(status),
    )
    with transactional(db):
        db.add(user)
    return user


def get_user_by_id(db: Session, *, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(code=error_codes.USER_NOT_FOUND, message=f"user_id {user_id} not found")
    return user

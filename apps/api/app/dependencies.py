from collections.abc import Generator
from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User

logger = structlog.get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# DbSession: request-scoped DB session that commits before the HTTP response is
# sent (scope="function"). The default scope="request" would defer commit until
# after the response — so a fast client polling for the result of a write may
# see stale data.
#
# Place DbSession before parameters that have defaults to satisfy Python's
# "non-default argument follows default argument" ordering rule.
DbSession = Annotated[Session, Depends(get_db, scope="function")]


def get_current_user(
    db: DbSession,
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    Dependency that extracts and validates the current user from the JWT token.
    Binds user_id to structlog context for the request lifecycle.
    """
    from app.services.auth import AuthService

    user = AuthService.get_user_from_token(db, token)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

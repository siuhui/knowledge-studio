from collections.abc import Generator

import structlog
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal

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


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    """
    Dependency that extracts and validates the current user from the JWT token.
    Binds user_id to structlog context for the request lifecycle.
    """
    from app.services.auth_service import AuthService

    user = AuthService.get_user_from_token(db, token)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user

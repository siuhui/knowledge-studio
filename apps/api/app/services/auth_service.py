import structlog
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    @staticmethod
    def register(db: Session, *, username: str, password: str) -> User:
        existing = UserRepository.get_by_username(db, username=username)
        if existing:
            raise ConflictError(
                code=ErrorCode.USERNAME_TAKEN,
                message=f"Username '{username}' is already taken",
            )

        user = User(
            username=username,
            password_hash=hash_password(password),
        )
        user = UserRepository.save(db, user=user)
        logger.info("user registered", user_id=user.id)
        return user

    @staticmethod
    def login(db: Session, *, username: str, password: str) -> str:
        user = UserRepository.get_by_username(db, username=username)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError(
                code=ErrorCode.INVALID_CREDENTIALS,
                message="Invalid username or password",
            )

        token = create_access_token(user.id)
        logger.info("user logged in", user_id=user.id)
        return token

    @staticmethod
    def get_user_from_token(db: Session, token: str) -> User:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise UnauthorizedError(
                    code=ErrorCode.TOKEN_INVALID,
                    message="Invalid token: missing subject",
                )
        except Exception:
            raise UnauthorizedError(
                code=ErrorCode.TOKEN_INVALID,
                message="Invalid or expired token",
            )

        user = UserRepository.get_by_id(db, user_id=user_id)
        if not user:
            raise UnauthorizedError(
                code=ErrorCode.TOKEN_INVALID,
                message="User not found",
            )
        return user

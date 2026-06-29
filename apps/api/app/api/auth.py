from fastapi import APIRouter

from app.core.response_codes import ResponseCode
from app.dependencies import DbSession
from app.schemas.auth import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from app.schemas.common import ApiResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[UserResponse])
def register(db: DbSession, payload: RegisterRequest) -> ApiResponse[UserResponse]:
    user = AuthService.register(db, username=payload.username, password=payload.password)
    return ApiResponse[UserResponse](
        code=ResponseCode.OK,
        message="User registered successfully",
        data=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=ApiResponse[AuthTokenResponse])
def login(db: DbSession, payload: LoginRequest) -> ApiResponse[AuthTokenResponse]:
    token = AuthService.login(db, username=payload.username, password=payload.password)
    return ApiResponse[AuthTokenResponse](
        code=ResponseCode.OK,
        message="Login successful",
        data=AuthTokenResponse(access_token=token),
    )

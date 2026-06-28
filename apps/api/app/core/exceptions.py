import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.core.response_codes import ResponseCode
from app.schemas.common import ApiResponse

logger = structlog.get_logger(__name__)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "app_error",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse[None](code=exc.code, message=exc.message, data=None).model_dump(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        message=str(exc),
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse[None](
            code=ResponseCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            data=None,
        ).model_dump(),
    )

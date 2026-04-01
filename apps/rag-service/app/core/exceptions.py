import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .error_codes import HTTP_ERROR, INTERNAL_SERVER_ERROR, VALIDATION_ERROR
from .errors import AppError
from .trace import get_trace_id

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
                "trace_id": get_trace_id(request),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        trace_id = get_trace_id(request)
        if isinstance(exc.detail, dict):
            payload = exc.detail
            payload.setdefault("trace_id", trace_id)
            payload.setdefault("data", None)
            payload.setdefault("code", HTTP_ERROR)
            payload.setdefault("message", "http error")
            return JSONResponse(status_code=exc.status_code, content=payload)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": HTTP_ERROR,
                "message": str(exc.detail),
                "data": None,
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": VALIDATION_ERROR,
                "message": "request validation failed",
                "data": {"errors": exc.errors()},
                "trace_id": get_trace_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        trace_id = get_trace_id(request)
        logger.exception("Unhandled exception, trace_id=%s", trace_id)
        return JSONResponse(
            status_code=500,
            content={
                "code": INTERNAL_SERVER_ERROR,
                "message": "internal server error",
                "data": None,
                "trace_id": trace_id,
            },
        )

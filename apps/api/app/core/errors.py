from app.core.response_codes import ResponseCode


class AppError(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, *, code: ResponseCode, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, *, code: ResponseCode, message: str):
        super().__init__(code=code, message=message, status_code=404)


class ValidationError(AppError):
    def __init__(self, *, code: ResponseCode, message: str):
        super().__init__(code=code, message=message, status_code=422)


class UnauthorizedError(AppError):
    def __init__(self, *, code: ResponseCode, message: str):
        super().__init__(code=code, message=message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, *, code: ResponseCode, message: str):
        super().__init__(code=code, message=message, status_code=403)


class ConflictError(AppError):
    def __init__(self, *, code: ResponseCode, message: str):
        super().__init__(code=code, message=message, status_code=409)

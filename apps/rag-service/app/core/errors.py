class AppError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str, data: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data


class NotFoundError(AppError):
    def __init__(self, *, code: str, message: str, data: dict | None = None):
        super().__init__(status_code=404, code=code, message=message, data=data)


class ConflictError(AppError):
    def __init__(self, *, code: str, message: str, data: dict | None = None):
        super().__init__(status_code=409, code=code, message=message, data=data)


class BadRequestError(AppError):
    def __init__(self, *, code: str, message: str, data: dict | None = None):
        super().__init__(status_code=400, code=code, message=message, data=data)


class PermissionDeniedError(AppError):
    def __init__(self, *, message: str = "permission denied", data: dict | None = None):
        from .error_codes import PERMISSION_DENIED

        super().__init__(status_code=403, code=PERMISSION_DENIED, message=message, data=data)

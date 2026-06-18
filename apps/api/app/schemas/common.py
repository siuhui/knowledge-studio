from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.error_codes import ErrorCode

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = Field(default=ErrorCode.VALIDATION_ERROR, description="Error code; OK on success")
    message: str = Field(default="", description="Human-readable message")
    data: T | None = Field(default=None, description="Response payload")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    code: str = Field(default="OK")
    message: str = Field(default="success")
    data: list[T] = Field(default_factory=list)
    meta: PaginationMeta

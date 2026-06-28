from pydantic import BaseModel, Field

from app.core.response_codes import ResponseCode


class ApiResponse[T](BaseModel):
    code: ResponseCode = Field(description="Status code; OK on success")
    message: str = Field(default="", description="Human-readable message")
    data: T | None = Field(default=None, description="Response payload")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse[T](ApiResponse[list[T]]):
    message: str = Field(default="success")
    data: list[T] = Field(default_factory=list)
    meta: PaginationMeta

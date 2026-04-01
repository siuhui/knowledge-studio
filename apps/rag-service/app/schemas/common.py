from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    code: str
    message: str
    data: None = None
    trace_id: str


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str
    data: T
    trace_id: str

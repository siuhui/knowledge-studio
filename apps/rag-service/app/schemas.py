from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

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


class IndexJobCreateRequest(BaseModel):
    source_id: str = Field(min_length=1)
    mode: Literal["incremental", "full"] = "incremental"


class IndexJobPayload(BaseModel):
    job_id: str
    status: Literal["queued", "running", "success", "failed"]


class IndexJobDetail(BaseModel):
    job_id: str
    source_id: str
    mode: Literal["incremental", "full"]
    status: Literal["queued", "running", "success", "failed"]
    error_message: str | None = None
    total_documents: int
    indexed_documents: int
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: Literal["local", "wiki"] = "local"
    sync_mode: Literal["scheduled", "manual"] = "scheduled"
    status: Literal["active", "paused", "error"] = "active"
    config_json: str | None = None


class SourceItem(BaseModel):
    id: str
    name: str
    source_type: str
    sync_mode: str
    status: str


class SourceListPayload(BaseModel):
    items: list[SourceItem]

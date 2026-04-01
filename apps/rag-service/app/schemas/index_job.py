from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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

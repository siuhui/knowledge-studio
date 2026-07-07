from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StudioTaskConfig(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None
    style: Literal["professional", "casual", "academic"] = "professional"
    length: Literal["short", "medium", "long"] = "medium"


class StudioTaskCreate(BaseModel):
    task_type: Literal["report"] = "report"
    title: str = Field(min_length=1, max_length=255)
    config: StudioTaskConfig


class StudioTaskItem(BaseModel):
    id: str
    task_type: str
    title: str
    status: str
    progress: float
    status_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class StudioTaskDetail(StudioTaskItem):
    knowledge_base_id: str
    config: dict[str, Any]
    output_metadata: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}

from typing import Literal

from pydantic import BaseModel, Field


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

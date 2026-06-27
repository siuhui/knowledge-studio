from datetime import datetime

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    type: str = Field(default="upload", pattern="^(upload)$")  # v0.1.0 only upload
    config: dict = Field(default_factory=dict)


class SourceItem(BaseModel):
    id: str
    knowledge_base_id: str
    type: str
    config: dict
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

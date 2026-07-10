from datetime import datetime

from pydantic import BaseModel, Field


class SourceConfigUpload(BaseModel):
    """Config shape for upload-type sources. Stores a reference to the MinIO object."""

    s3_key: str = Field(min_length=1, max_length=1024)
    original_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=0)
    mime_type: str = Field(default="application/octet-stream")
    format: str = Field(min_length=1, max_length=50)


class SourceCreate(BaseModel):
    type: str = Field(default="upload", pattern="^(upload|url)$")
    config: dict[str, object] | None = None


class SourceItem(BaseModel):
    id: str
    knowledge_base_id: str
    type: str
    config: dict[str, object]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

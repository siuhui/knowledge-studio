from datetime import datetime

from pydantic import BaseModel


class DocumentItem(BaseModel):
    id: str
    source_id: str | None
    title: str
    source_format: str
    status: str
    chunk_status: str | None = None
    embed_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChunkItem(BaseModel):
    id: str
    chunk_index: int
    content: str
    token_count: int
    start_offset: int
    end_offset: int
    section_path: list[str]
    heading_level: int = 0

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentItem):
    chunk_count: int
    truncated: bool
    chunks: list[ChunkItem]

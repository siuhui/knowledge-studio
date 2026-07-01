from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    reference_document_ids: list[str] | None = None


class MessageItem(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    citations: list[dict[str, Any]] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionItem(BaseModel):
    id: str
    knowledge_base_id: str
    user_id: str
    title: str
    message_count: int
    reference_document_ids: list[str] | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(SessionItem):
    messages: list[MessageItem]

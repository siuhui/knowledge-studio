from pydantic import BaseModel, Field

from app.schemas.retrieval.citation import Citation


class ChatRequest(BaseModel):
    knowledge_base_id: str
    session_id: str | None = Field(default=None)
    content: str = Field(min_length=1, max_length=2000)
    reference_document_ids: list[str] | None = Field(
        default=None,
        description="Document scope for new sessions only; ignored for existing sessions (use session PATCH instead)",
    )
    search_mode: str | None = Field(
        default=None,
        description="Force search mode ('direct'/'agentic'), or null for LLM auto-routing",
    )


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[Citation]
    persisted: bool

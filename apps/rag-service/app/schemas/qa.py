from pydantic import BaseModel, Field

from .retrieval import CitationItem


class QAAskRequest(BaseModel):
    kb_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


class QAAskPayload(BaseModel):
    answer: str
    grounded: bool
    citations: list[CitationItem]

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    chunk_id: str
    doc_id: str
    score: float
    snippet: str


class RetrievalQueryRequest(BaseModel):
    kb_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalQueryPayload(BaseModel):
    items: list[CitationItem]

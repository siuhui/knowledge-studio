from typing import Any

from pydantic import BaseModel

from app.schemas.retrieval.citation import Citation


class RetrievalChunk(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_title: str
    section_path: list[str] = []
    citation: Citation


class RetrievalQueryResponse(BaseModel):
    query: str
    results: list[RetrievalChunk]
    agent_steps: list[dict[str, Any]] | None = None

from pydantic import BaseModel

from app.schemas.retrieval.citation import Citation


class RetrievalChunk(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_title: str
    citation: Citation


class RetrievalQueryResponse(BaseModel):
    query: str
    results: list[RetrievalChunk]


class QaResponse(BaseModel):
    query: str
    answer: str
    sources: list[Citation]

from pydantic import BaseModel, Field


class RetrievalQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    knowledge_base_id: str
    top_k: int = Field(default=10, ge=1, le=50)

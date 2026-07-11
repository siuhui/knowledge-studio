from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    content_snippet: str = Field(description="Relevant excerpt from the chunk")
    start_offset: int = 0
    end_offset: int = 0

"""Build citation objects from retrieval results."""

from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.retrieval.citation import Citation


def build_citations(results: list[tuple[Chunk, Document, float]]) -> list[Citation]:
    """Convert retrieval results to citation objects."""
    citations = []
    seen = set()
    for chunk, doc, score in results:
        if doc.id in seen:
            continue
        seen.add(doc.id)
        citations.append(
            Citation(
                document_id=doc.id,
                document_title=doc.title,
                chunk_index=chunk.chunk_index,
                content_snippet=chunk.content[:200],
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
        )
    return citations

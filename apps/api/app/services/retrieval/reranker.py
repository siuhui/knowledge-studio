"""Re-ranker: refines retrieval results.

v0.1: identity pass — RRF fusion is sufficient for initial quality targets.
v0.2+: could use cross-encoder or LLM-based re-ranking.
"""

from app.models.chunk import Chunk
from app.models.document import Document


def rerank(
    results: list[tuple[Chunk, Document, float]],
) -> list[tuple[Chunk, Document, float]]:
    """Re-rank search results. Currently a pass-through."""
    return results

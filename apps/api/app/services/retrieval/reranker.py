"""Re-ranker: refines retrieval results.

v0.1.0: identity pass — RRF fusion is sufficient for initial quality targets.
v0.2.0+: could use cross-encoder or LLM-based re-ranking.
"""

from app.models.chunk import Chunk


def rerank(
    results: list[tuple[Chunk, float]],
) -> list[tuple[Chunk, float]]:
    """Re-rank search results. Currently a pass-through."""
    return results

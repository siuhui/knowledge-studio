from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import PermissionDeniedError
from ..models import KnowledgeChunk
from ..schemas import CitationItem
from .access_control import can_access, resolve_kb_role
from .knowledge_bases_service import get_knowledge_base_by_id


def _score(query: str, content: str) -> float:
    terms = [term for term in query.lower().split() if term]
    if not terms:
        return 0.0
    text = content.lower()
    hits = sum(text.count(term) for term in terms)
    return float(hits)


def query_kb_chunks(db: Session, *, kb_id: str, user_id: str, query: str, top_k: int) -> list[CitationItem]:
    _ = get_knowledge_base_by_id(db, knowledge_base_id=kb_id)
    role, _ = resolve_kb_role(db, user_id=user_id, knowledge_base_id=kb_id)
    if not can_access("read", role):
        raise PermissionDeniedError(message="read permission denied for this knowledge base")

    rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.permission_scope == kb_id)).all()
    chunks = cast(list[KnowledgeChunk], rows)

    ranked: list[tuple[float, KnowledgeChunk]] = []
    for chunk in chunks:
        score = _score(query, chunk.content)
        if score > 0:
            ranked.append((score, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    top = ranked[:top_k]
    return [
        CitationItem(
            chunk_id=chunk.id,
            doc_id=chunk.doc_id,
            score=score,
            snippet=chunk.content[:280],
        )
        for score, chunk in top
    ]

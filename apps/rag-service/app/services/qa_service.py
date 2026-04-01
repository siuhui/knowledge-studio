from sqlalchemy.orm import Session

from ..schemas import QAAskPayload
from .retrieval_service import query_kb_chunks


def ask_kb_question(db: Session, *, kb_id: str, user_id: str, question: str, top_k: int) -> QAAskPayload:
    citations = query_kb_chunks(db, kb_id=kb_id, user_id=user_id, query=question, top_k=top_k)
    if not citations:
        return QAAskPayload(
            answer="未检索到相关内容，请调整关键词后重试。",
            grounded=False,
            citations=[],
        )

    points = [f"- {citation.snippet}" for citation in citations[:3]]
    answer = "根据知识库检索结果，相关要点如下：\n" + "\n".join(points)
    return QAAskPayload(answer=answer, grounded=True, citations=citations)

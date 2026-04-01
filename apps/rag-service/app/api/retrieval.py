from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import ApiResponse, RetrievalQueryPayload, RetrievalQueryRequest
from ..services.retrieval_service import query_kb_chunks

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


@router.post("/query", response_model=ApiResponse[RetrievalQueryPayload])
def query_retrieval(
    payload: RetrievalQueryRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[RetrievalQueryPayload]:
    items = query_kb_chunks(
        db,
        kb_id=payload.kb_id,
        user_id=payload.user_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return ApiResponse[RetrievalQueryPayload](
        message="success",
        data=RetrievalQueryPayload(items=items),
        trace_id=get_trace_id(request),
    )

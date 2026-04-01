from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import ApiResponse, QAAskPayload, QAAskRequest
from ..services.qa_service import ask_kb_question

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


@router.post("/ask", response_model=ApiResponse[QAAskPayload])
def ask_question(payload: QAAskRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[QAAskPayload]:
    data = ask_kb_question(
        db,
        kb_id=payload.kb_id,
        user_id=payload.user_id,
        question=payload.question,
        top_k=payload.top_k,
    )
    return ApiResponse[QAAskPayload](
        message="success",
        data=data,
        trace_id=get_trace_id(request),
    )

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.retrieval.request import QaRequest, RetrievalQueryRequest
from app.schemas.retrieval.response import QaResponse, RetrievalQueryResponse
from app.services.retrieval.service import RetrievalService

router = APIRouter(tags=["retrieval"])


@router.post("/api/v1/retrieval/query", response_model=ApiResponse[RetrievalQueryResponse])
def search(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RetrievalQueryResponse]:
    result = RetrievalService.search(
        db,
        query=payload.query,
        knowledge_base_id=payload.knowledge_base_id,
        top_k=payload.top_k,
    )
    return ApiResponse[RetrievalQueryResponse](code="OK", message="success", data=result)


@router.post("/api/v1/qa/ask", response_model=ApiResponse[QaResponse])
def ask(
    payload: QaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[QaResponse]:
    result = RetrievalService.ask(
        db,
        query=payload.query,
        knowledge_base_id=payload.knowledge_base_id,
        top_k=payload.top_k,
    )
    return ApiResponse[QaResponse](code="OK", message="success", data=result)

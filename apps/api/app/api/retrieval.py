from fastapi import APIRouter

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.schemas.retrieval.request import QaRequest, RetrievalQueryRequest
from app.schemas.retrieval.response import QaResponse, RetrievalQueryResponse
from app.services.retrieval.service import RetrievalService

router = APIRouter(tags=["retrieval"])


@router.post("/api/v1/retrieval/query", response_model=ApiResponse[RetrievalQueryResponse])
def search(
    db: DbSession,
    current_user: CurrentUser,
    payload: RetrievalQueryRequest,
) -> ApiResponse[RetrievalQueryResponse]:
    result = RetrievalService.search(
        db,
        query=payload.query,
        knowledge_base_id=payload.knowledge_base_id,
        top_k=payload.top_k,
    )
    return ApiResponse[RetrievalQueryResponse](code=ResponseCode.OK, message="success", data=result)


@router.post("/api/v1/qa/ask", response_model=ApiResponse[QaResponse])
def ask(
    db: DbSession,
    current_user: CurrentUser,
    payload: QaRequest,
) -> ApiResponse[QaResponse]:
    result = RetrievalService.ask(
        db,
        query=payload.query,
        knowledge_base_id=payload.knowledge_base_id,
        top_k=payload.top_k,
    )
    return ApiResponse[QaResponse](code=ResponseCode.OK, message="success", data=result)

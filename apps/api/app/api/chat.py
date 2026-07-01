from fastapi import APIRouter

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ApiResponse
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat/messages", response_model=ApiResponse[ChatResponse])
def send_message(
    db: DbSession,
    current_user: CurrentUser,
    payload: ChatRequest,
) -> ApiResponse[ChatResponse]:
    result = ChatService.send_message(
        db,
        kb_id=payload.knowledge_base_id,
        user_id=current_user.id,
        session_id=payload.session_id,
        content=payload.content,
        reference_document_ids=payload.reference_document_ids,
    )
    return ApiResponse[ChatResponse](code=ResponseCode.OK, message="success", data=result)

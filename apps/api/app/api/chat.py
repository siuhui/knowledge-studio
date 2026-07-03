from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession, DbSessionStreaming
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
        search_strategy=payload.search_strategy,
    )
    return ApiResponse[ChatResponse](code=ResponseCode.OK, message="success", data=result)


@router.post("/api/v1/chat/messages/stream")
async def send_message_stream(
    db: DbSessionStreaming,
    current_user: CurrentUser,
    payload: ChatRequest,
) -> StreamingResponse:
    """Stream chat response as SSE events.

    Event types (each a JSON object in the ``data:`` field):

    - ``session``        — session_id, user_msg_id (first event)
    - ``agent_progress`` — retrieval progress indicator (optional, before ``token``)
    - ``token``          — LLM text chunk (one or more)
    - ``citation``       — deduplicated source citations
    - ``done``           — persisted flag + ai_message_id
    - ``error``          — error message (optional, before ``done``)
    """

    # Extract user_id before entering the async generator — the current_user
    # ORM instance will be detached once the request-scoped DB session closes.
    # Nb. DbSessionStreaming (scope="request") keeps the session alive for the
    # full response lifecycle, including StreamingResponse body consumption.
    user_id = current_user.id

    async def event_generator() -> AsyncIterator[str]:
        async for event_json in ChatService.stream_message(
            db,
            kb_id=payload.knowledge_base_id,
            user_id=user_id,
            session_id=payload.session_id,
            content=payload.content,
            reference_document_ids=payload.reference_document_ids,
            search_strategy=payload.search_strategy,
        ):
            yield f"data: {event_json}\n\n"

        # Extra newline signals end-of-stream per SSE spec
        yield "\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )

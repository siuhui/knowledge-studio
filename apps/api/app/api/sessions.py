from fastapi import APIRouter, Query

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.schemas.session import (
    SessionDetail,
    SessionItem,
    SessionUpdate,
)
from app.services.session import SessionService

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{knowledge_base_id}/sessions",
    tags=["sessions"],
)


@router.get("", response_model=PaginatedResponse[SessionItem])
def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SessionItem]:
    sessions, total = SessionService.list_by_kb(
        db,
        kb_id=knowledge_base_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )

    items = []
    for session in sessions:
        msg_count = getattr(session, "_message_count", 0)
        items.append(
            SessionItem(
                id=session.id,
                knowledge_base_id=session.knowledge_base_id,
                user_id=session.user_id,
                title=session.title,
                message_count=msg_count,
                reference_document_ids=session.reference_document_ids,
                last_message_at=session.last_message_at,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )

    return PaginatedResponse[SessionItem](
        code=ResponseCode.OK,
        message="success",
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.get("/{session_id}", response_model=ApiResponse[SessionDetail])
def get_session(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    session_id: str,
) -> ApiResponse[SessionDetail]:
    session = SessionService.get_by_id(db, session_id=session_id, kb_id=knowledge_base_id, user_id=current_user.id)
    msg_count = len(session.messages) if session.messages else 0
    result = SessionDetail(
        id=session.id,
        knowledge_base_id=session.knowledge_base_id,
        user_id=session.user_id,
        title=session.title,
        message_count=msg_count,
        reference_document_ids=session.reference_document_ids,
        last_message_at=session.last_message_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[m for m in session.messages] if session.messages else [],
    )
    return ApiResponse[SessionDetail](code=ResponseCode.OK, message="success", data=result)


@router.patch("/{session_id}", response_model=ApiResponse[SessionItem])
def update_session(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    session_id: str,
    payload: SessionUpdate,
) -> ApiResponse[SessionItem]:
    session = SessionService.update(
        db,
        session_id=session_id,
        kb_id=knowledge_base_id,
        user_id=current_user.id,
        title=payload.title,
        update_doc_ids="reference_document_ids" in payload.model_fields_set,
        reference_document_ids=payload.reference_document_ids,
    )
    msg_count = len(session.messages) if session.messages else 0
    result = SessionItem(
        id=session.id,
        knowledge_base_id=session.knowledge_base_id,
        user_id=session.user_id,
        title=session.title,
        message_count=msg_count,
        reference_document_ids=session.reference_document_ids,
        last_message_at=session.last_message_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
    return ApiResponse[SessionItem](code=ResponseCode.OK, message="success", data=result)


@router.delete("/{session_id}", response_model=ApiResponse[None])
def delete_session(
    db: DbSession,
    current_user: CurrentUser,
    knowledge_base_id: str,
    session_id: str,
) -> ApiResponse[None]:
    SessionService.delete(db, session_id=session_id, kb_id=knowledge_base_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="Session deleted", data=None)

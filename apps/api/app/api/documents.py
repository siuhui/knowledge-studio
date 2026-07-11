from typing import Any

from fastapi import APIRouter, Query

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.schemas.document import ChunkItem, DocumentDetail, DocumentItem
from app.services.document import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/{document_id}", response_model=ApiResponse[dict[str, Any]])
def get_document(
    db: DbSession,
    current_user: CurrentUser,
    document_id: str,
    include_full_text: bool = Query(False, description="Include the full parsed text for rendering"),
) -> ApiResponse[dict[str, Any]]:
    document = DocumentService.get_by_id(db, document_id=document_id, user_id=current_user.id)
    data = DocumentItem.model_validate(document).model_dump(mode="json")
    if include_full_text:
        data["full_text"] = document.full_text
    return ApiResponse[dict[str, Any]](
        code=ResponseCode.OK,
        message="success",
        data=data,
    )


@router.get("/{document_id}/chunks", response_model=ApiResponse[dict[str, Any]])
def get_document_chunks(
    db: DbSession,
    current_user: CurrentUser,
    document_id: str,
) -> ApiResponse[dict[str, Any]]:
    """Get document metadata and its indexed chunks.

    Returns chunk content in order so the frontend can render a continuous
    document reader.  Chunk technical metadata (chunk_index, token_count) is
    included but hidden by default in the UI.

    start_char / end_char / metadata are reserved for future citation→location
    jumping and return null in v1.
    """
    result = DocumentService.get_chunks(db, document_id=document_id, user_id=current_user.id)
    return ApiResponse[dict[str, Any]](
        code=ResponseCode.OK,
        message="success",
        data=DocumentDetail(
            **DocumentItem.model_validate(result["document"]).model_dump(),
            chunk_count=result["total_count"],
            truncated=result["truncated"],
            chunks=[ChunkItem.model_validate(c) for c in result["chunks"]],
        ).model_dump(mode="json"),
    )


@router.delete("/{document_id}", response_model=ApiResponse[None])
def delete_document(
    db: DbSession,
    current_user: CurrentUser,
    document_id: str,
) -> ApiResponse[None]:
    DocumentService.delete(db, document_id=document_id, user_id=current_user.id)
    return ApiResponse[None](code=ResponseCode.OK, message="Document deleted", data=None)

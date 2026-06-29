from typing import Any

import structlog
from fastapi import APIRouter, File, Form, UploadFile

from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.services.document import DocumentService
from app.services.index_pipeline import index_document
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/upload", response_model=ApiResponse[dict[str, Any]])
async def upload_document(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    source_id: str = Form(...),
) -> ApiResponse[dict[str, Any]]:
    # Verify source exists
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)

    # Read file bytes
    raw_bytes = await file.read()

    # Run indexing pipeline: parse → document → chunk
    document_id = index_document(
        db,
        raw_bytes=raw_bytes,
        filename=file.filename or "unknown",
        source_id=source.id,
    )

    logger.info(
        "file uploaded and indexed",
        filename=file.filename,
        document_id=document_id,
        source_id=source_id,
    )

    return ApiResponse[dict[str, Any]](
        code=ResponseCode.OK,
        message="File uploaded and indexed successfully",
        data={"document_id": document_id},
    )


@router.get("/{document_id}", response_model=ApiResponse[dict[str, Any]])
def get_document(
    db: DbSession,
    current_user: CurrentUser,
    document_id: str,
) -> ApiResponse[dict[str, Any]]:
    document = DocumentService.get_by_id(db, document_id=document_id)
    return ApiResponse[dict[str, Any]](
        code=ResponseCode.OK,
        message="success",
        data={
            "id": document.id,
            "source_id": document.source_id,
            "title": document.title,
            "source_format": document.source_format,
            "status": document.status,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        },
    )


@router.delete("/{document_id}", response_model=ApiResponse[None])
def delete_document(
    db: DbSession,
    current_user: CurrentUser,
    document_id: str,
) -> ApiResponse[None]:
    DocumentService.delete(db, document_id=document_id)
    return ApiResponse[None](code=ResponseCode.OK, message="Document deleted", data=None)

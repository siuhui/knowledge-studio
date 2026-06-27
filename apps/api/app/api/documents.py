import structlog
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.response_codes import ResponseCode
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.document_service import DocumentService
from app.services.indexing_service import index_document
from app.services.source_service import SourceService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/upload", response_model=ApiResponse[dict])
async def upload_document(
    file: UploadFile = File(...),
    source_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    # Verify source exists
    source = SourceService.get_by_id(db, source_id=source_id)

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

    return ApiResponse[dict](
        code=ResponseCode.OK,
        message="File uploaded and indexed successfully",
        data={"document_id": document_id},
    )


@router.get("/{document_id}", response_model=ApiResponse[dict])
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    document = DocumentService.get_by_id(db, document_id=document_id)
    return ApiResponse[dict](
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
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[None]:
    DocumentService.delete(db, document_id=document_id)
    return ApiResponse[None](code=ResponseCode.OK, message="Document deleted", data=None)

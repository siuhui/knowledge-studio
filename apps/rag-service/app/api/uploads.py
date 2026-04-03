from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.trace import get_trace_id
from ..database import get_db
from ..schemas import (
    ApiResponse,
    UploadCompletePayload,
    UploadCompleteRequest,
    UploadPresignPayload,
    UploadPresignRequest,
    UploadedObjectItem,
    UploadedObjectListPayload,
)
from ..services.uploads_service import (
    complete_upload,
    create_upload_presign,
    delete_uploaded_object,
    get_uploaded_object_detail,
    list_uploaded_objects,
)

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("/presign", response_model=ApiResponse[UploadPresignPayload])
def create_presign(
    payload: UploadPresignRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[UploadPresignPayload]:
    data = create_upload_presign(
        db=db,
        user_id=payload.user_id,
        kb_id=payload.kb_id,
        filename=payload.filename,
        content_type=payload.content_type,
    )
    return ApiResponse[UploadPresignPayload](
        message="success",
        data=data,
        trace_id=get_trace_id(request),
    )


@router.post("/complete", response_model=ApiResponse[UploadCompletePayload])
def complete(
    payload: UploadCompleteRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[UploadCompletePayload]:
    data = complete_upload(
        db=db,
        kb_id=payload.kb_id,
        bucket=payload.bucket,
        object_key=payload.object_key,
        etag=payload.etag,
        uploader_user_id=payload.uploader_user_id,
    )
    return ApiResponse[UploadCompletePayload](
        message="accepted",
        data=data,
        trace_id=get_trace_id(request),
    )


@router.get("", response_model=ApiResponse[UploadedObjectListPayload])
def list_uploads(
    kb_id: str, user_id: str, request: Request, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)
) -> ApiResponse[UploadedObjectListPayload]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    data = list_uploaded_objects(
        db=db,
        kb_id=kb_id,
        user_id=user_id,
        page=safe_page,
        page_size=safe_page_size,
    )
    return ApiResponse[UploadedObjectListPayload](
        message="success",
        data=data,
        trace_id=get_trace_id(request),
    )


@router.get("/{uploaded_object_id}", response_model=ApiResponse[UploadedObjectItem])
def get_upload_detail(
    uploaded_object_id: str, user_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[UploadedObjectItem]:
    data = get_uploaded_object_detail(db=db, uploaded_object_id=uploaded_object_id, user_id=user_id)
    return ApiResponse[UploadedObjectItem](
        message="success",
        data=data,
        trace_id=get_trace_id(request),
    )


@router.delete("/{uploaded_object_id}", response_model=ApiResponse[UploadCompletePayload])
def delete_upload(
    uploaded_object_id: str, user_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[UploadCompletePayload]:
    delete_uploaded_object(db=db, uploaded_object_id=uploaded_object_id, user_id=user_id)
    return ApiResponse[UploadCompletePayload](
        message="accepted",
        data=UploadCompletePayload(accepted=True, uploaded_object_id=uploaded_object_id),
        trace_id=get_trace_id(request),
    )

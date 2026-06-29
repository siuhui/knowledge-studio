"""Upload API — presigned POST and complete callbacks, scoped to a Source.

File bytes go Browser → MinIO directly (presigned POST).
Backend only handles metadata: presign (auth + key) and complete (validation + activate).

Source is created first (pending), then upload fills it. Object key format:
    uploads/{kb_id}/{source_id}/{opaque}/{sanitized_name}
The source_id in the path enables per-source prefix cleanup on delete.
"""

import secrets
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks

from app.config import settings
from app.core.errors import ValidationError
from app.core.response_codes import ResponseCode
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.schemas.upload import (
    PresignRequest,
    PresignResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
)
from app.services.index_pipeline import run_index_pipeline
from app.services.object_storage import ObjectStorageService, sanitize_filename
from app.services.source import SourceService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["sources"])

ALLOWED_EXTENSIONS = frozenset({".pdf", ".md", ".markdown", ".txt", ".text"})

UPLOAD_PREFIX = "uploads"


def _make_object_key(kb_id: str, source_id: str, filename: str) -> str:
    """Server-generated object key with source-scoped directory.

    Format: uploads/{kb_id}/{source_id}/{opaque}/{sanitized_name}
    - kb_id: enables ownership validation in /complete
    - source_id: enables per-source prefix cleanup on delete
    - opaque: 128-bit random token prevents guessing valid keys
    - sanitized_name: human-readable filename leaf
    """
    safe_kb = str(kb_id)
    safe_source = str(source_id)
    safe_name = sanitize_filename(filename)
    # Reject empty and extension-only names (e.g. ".pdf", ".gitignore")
    if not safe_name or not Path(safe_name).stem:
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message="Filename is empty after sanitization",
        )
    opaque = secrets.token_urlsafe(16)  # 128 bits of entropy
    return f"{UPLOAD_PREFIX}/{safe_kb}/{safe_source}/{opaque}/{safe_name}"


@router.post(
    "/api/v1/sources/{source_id}/uploads/presign",
    response_model=ApiResponse[PresignResponse],
)
def create_presign(
    db: DbSession,
    current_user: CurrentUser,
    source_id: str,
    payload: PresignRequest,
) -> ApiResponse[PresignResponse]:
    """Generate a presigned POST URL for browser-to-MinIO direct upload."""
    # Verify source exists and user owns its knowledge base
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)

    # Only pending sources can receive uploads
    if source.status != "pending":
        raise ValidationError(
            code=ResponseCode.SOURCE_STATUS_INVALID,
            message=f"Cannot upload to source in '{source.status}' state",
        )

    # Validate file extension (primary check — not relying on Content-Type)
    suffix = Path(payload.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            code=ResponseCode.DOCUMENT_UNSUPPORTED_FORMAT,
            message=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    object_key = _make_object_key(source.knowledge_base_id, source_id, payload.filename)

    cfg = settings.object_storage
    upload_url, upload_fields = ObjectStorageService.generate_presigned_post(
        key=object_key,
    )

    logger.info(
        "presigned upload created",
        source_id=source_id,
        kb_id=source.knowledge_base_id,
        filename=payload.filename,
        object_key=object_key,
    )

    return ApiResponse[PresignResponse](
        code=ResponseCode.OK,
        message="Presigned upload URL generated",
        data=PresignResponse(
            provider="minio",
            bucket=cfg.bucket,
            object_key=object_key,
            upload_url=upload_url,
            upload_fields=upload_fields,
            expires_in=cfg.presign_expire_seconds,
            max_size_bytes=cfg.max_upload_size_bytes,
        ),
    )


@router.post(
    "/api/v1/sources/{source_id}/uploads/complete",
    response_model=ApiResponse[UploadCompleteResponse],
)
def complete_upload(
    db: DbSession,
    current_user: CurrentUser,
    source_id: str,
    payload: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
) -> ApiResponse[UploadCompleteResponse]:
    """Validate uploaded object, activate source, and trigger indexing."""
    # Verify source exists and user owns its knowledge base
    source = SourceService.get_by_id(db, source_id=source_id, user_id=current_user.id)

    # Only pending sources can be completed
    if source.status != "pending":
        raise ValidationError(
            code=ResponseCode.SOURCE_STATUS_INVALID,
            message=f"Source is already {source.status}",
        )

    # Verify bucket matches config
    if payload.bucket != settings.object_storage.bucket:
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message=f"Unknown bucket: {payload.bucket}",
        )

    # Validate object_key belongs to this source: prefix must match
    expected_prefix = f"{UPLOAD_PREFIX}/{source.knowledge_base_id}/{source_id}/"
    if not payload.object_key.startswith(expected_prefix):
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message=f"Object key does not match source {source_id}",
        )

    # Head the object — NotFoundError (404) and AppError (502)
    # are raised by ObjectStorageService for different failure modes
    head = ObjectStorageService.head_object(key=payload.object_key)

    content_length = int(head.get("ContentLength", 0) or 0)
    if content_length <= 0:
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message="Uploaded object is empty",
        )
    if content_length > settings.object_storage.max_upload_size_bytes:
        raise ValidationError(
            code=ResponseCode.VALIDATION_ERROR,
            message=f"File exceeds max size of {settings.object_storage.max_upload_size_bytes // 1024 // 1024}MB",
        )

    # Extract the original filename from the object_key path
    # (not from Content-Type header — that's client-supplied and forgeable)
    original_filename = Path(payload.object_key).name
    content_type = str(head.get("ContentType", ""))
    suffix = Path(original_filename).suffix.lower().lstrip(".")

    # Build config and transition source pending -> active
    config: dict[str, object] = {
        "s3_key": payload.object_key,
        "original_name": original_filename,
        "file_size": content_length,
        "mime_type": content_type,
        "format": suffix,
    }
    SourceService.update_config_and_activate(db, source_id=source_id, config=config)

    # Commit is handled by DbSession (scope="function") — runs before
    # the response is sent and before background tasks fire, so the
    # indexing task sees the active status.

    # Schedule background indexing (creates its own DB session)
    background_tasks.add_task(
        run_index_pipeline,
        source_id=source_id,
        s3_key=payload.object_key,
        filename=original_filename,
    )

    logger.info(
        "upload completed and source activated",
        source_id=source_id,
        object_key=payload.object_key,
        size_bytes=content_length,
    )

    return ApiResponse[UploadCompleteResponse](
        code=ResponseCode.OK,
        message="Upload validated and source activated",
        data=UploadCompleteResponse(
            accepted=True,
            object_key=payload.object_key,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=content_length,
        ),
    )

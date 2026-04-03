import datetime as dt
import hashlib
import importlib
import re
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..core import error_codes
from ..core.errors import AppError, BadRequestError, NotFoundError, PermissionDeniedError
from ..core.uow import transactional
from ..models import KnowledgeBase, UploadedObject, UploadedObjectStatus
from ..schemas import UploadCompletePayload, UploadPresignPayload, UploadedObjectItem, UploadedObjectListPayload
from .access_control import can_access, resolve_kb_role
from .knowledge_bases_service import get_knowledge_base_by_id

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
}
_EXT_TO_CONTENT_TYPE = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".txt": "text/plain",
}
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _require_storage_config() -> None:
    if not settings.object_storage_endpoint or not settings.object_storage_bucket:
        raise AppError(
            status_code=500,
            code=error_codes.UPLOAD_STORAGE_NOT_CONFIGURED,
            message="object storage is not configured",
        )


def _encode_base32_crockford(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def _new_ulid() -> str:
    now_utc = dt.datetime.now(dt.timezone.utc)
    timestamp_ms = int(now_utc.timestamp() * 1000)
    random_bits = secrets.randbits(80)
    return _encode_base32_crockford(timestamp_ms, 10) + _encode_base32_crockford(random_bits, 16)


def _slugify(text: str, *, default: str = "kb") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:60] if slug else default


def _sanitize_filename(filename: str) -> str:
    safe_name = Path(filename).name.strip()
    safe_name = safe_name.replace("\\", "_").replace("/", "_")
    if not safe_name or len(safe_name) > 255 or safe_name in {".", ".."}:
        raise BadRequestError(code=error_codes.UPLOAD_INVALID_FILENAME, message="invalid filename")
    return safe_name


def _validate_file(filename: str, content_type: str) -> tuple[str, str]:
    safe_name = _sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise BadRequestError(
            code=error_codes.UPLOAD_FORBIDDEN_EXTENSION,
            message=f"unsupported file extension: {suffix}",
        )
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise BadRequestError(
            code=error_codes.UPLOAD_INVALID_CONTENT_TYPE,
            message=f"unsupported content_type: {content_type}",
        )
    return safe_name, suffix


def _filename_hash(safe_name: str) -> str:
    digest = hashlib.sha1(safe_name.encode("utf-8")).hexdigest()
    return digest[:12]


def _build_object_key(*, kb_id: str, kb_slug: str, suffix: str, safe_name: str) -> str:
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    ulid = _new_ulid()
    short_hash = _filename_hash(safe_name)
    return f"kb/{kb_id}/{kb_slug}/raw/{day}/{ulid}_{short_hash}{suffix}"


def _get_s3_client():
    _require_storage_config()
    try:
        boto3 = importlib.import_module("boto3")
    except Exception as exc:
        raise AppError(
            status_code=500,
            code=error_codes.UPLOAD_PRESIGN_FAILED,
            message="boto3 not installed, unable to access object storage",
        ) from exc
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
    )


def _build_presigned_post(*, object_key: str, content_type: str, original_filename: str) -> tuple[str, dict[str, str]]:
    client = _get_s3_client()
    try:
        fields = {
            "Content-Type": content_type,
            "x-amz-meta-original-filename": original_filename,
        }
        conditions: list[Any] = [
            {"Content-Type": content_type},
            {"x-amz-meta-original-filename": original_filename},
            ["content-length-range", 1, settings.object_storage_max_upload_size_bytes],
        ]
        result = client.generate_presigned_post(
            Bucket=settings.object_storage_bucket,
            Key=object_key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=settings.object_storage_presign_expire_seconds,
        )
        return str(result["url"]), dict(result["fields"])
    except Exception as exc:
        raise AppError(
            status_code=500,
            code=error_codes.UPLOAD_PRESIGN_FAILED,
            message=f"failed to generate presigned post: {exc}",
        ) from exc


def _assert_kb_write_permission(db: Session, *, kb: KnowledgeBase, user_id: str) -> None:
    role, _ = resolve_kb_role(db, user_id=user_id, knowledge_base_id=kb.id)
    if not can_access("write", role):
        raise PermissionDeniedError(message="write permission denied for this knowledge base")


def _assert_kb_read_permission(db: Session, *, kb: KnowledgeBase, user_id: str) -> None:
    role, _ = resolve_kb_role(db, user_id=user_id, knowledge_base_id=kb.id)
    if not can_access("read", role):
        raise PermissionDeniedError(message="read permission denied for this knowledge base")


def create_upload_presign(*, db: Session, user_id: str, kb_id: str, filename: str, content_type: str) -> UploadPresignPayload:
    kb = get_knowledge_base_by_id(db, knowledge_base_id=kb_id)
    _assert_kb_write_permission(db, kb=kb, user_id=user_id)
    safe_name, suffix = _validate_file(filename=filename, content_type=content_type)
    kb_slug = _slugify(kb.name)
    object_key = _build_object_key(kb_id=kb_id, kb_slug=kb_slug, suffix=suffix, safe_name=safe_name)
    upload_url, upload_fields = _build_presigned_post(
        object_key=object_key,
        content_type=content_type,
        original_filename=safe_name,
    )
    return UploadPresignPayload(
        provider=settings.object_storage_provider,
        bucket=settings.object_storage_bucket,
        object_key=object_key,
        upload_method="POST",
        upload_url=upload_url,
        upload_fields=upload_fields,
        expires_in=settings.object_storage_presign_expire_seconds,
        max_size_bytes=settings.object_storage_max_upload_size_bytes,
    )


def _head_object(*, bucket: str, object_key: str) -> dict[str, Any]:
    client = _get_s3_client()
    try:
        return dict(client.head_object(Bucket=bucket, Key=object_key))
    except Exception as exc:
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_NOT_FOUND,
            message=f"uploaded object not found: {object_key}",
        ) from exc


def _delete_object(*, bucket: str, object_key: str) -> None:
    client = _get_s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except Exception as exc:
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_NOT_FOUND,
            message=f"failed to delete object: {object_key}",
        ) from exc


def _metadata_filename(head: dict[str, Any], object_key: str) -> str:
    metadata = head.get("Metadata")
    if isinstance(metadata, dict):
        value = metadata.get("original-filename")
        if isinstance(value, str) and value.strip():
            return _sanitize_filename(value)
    return Path(object_key).name


def _to_uploaded_object_item(row: UploadedObject) -> UploadedObjectItem:
    return UploadedObjectItem(
        id=row.id,
        kb_id=row.kb_id,
        bucket=row.bucket,
        object_key=row.object_key,
        original_filename=row.original_filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        etag=row.etag,
        status=row.status.value,
        index_error_message=row.index_error_message,
        uploader_user_id=row.uploader_user_id,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def complete_upload(
    *,
    db: Session,
    kb_id: str,
    bucket: str,
    object_key: str,
    etag: str | None,
    uploader_user_id: str | None = None,
) -> UploadCompletePayload:
    _ = etag
    kb = get_knowledge_base_by_id(db, knowledge_base_id=kb_id)
    if uploader_user_id:
        _assert_kb_write_permission(db, kb=kb, user_id=uploader_user_id)

    expected_prefix = f"kb/{kb_id}/"
    if bucket != settings.object_storage_bucket or not object_key.startswith(expected_prefix):
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_KEY_INVALID,
            message="object key does not match kb scope",
        )

    head = _head_object(bucket=bucket, object_key=object_key)
    content_length = int(head.get("ContentLength", 0) or 0)
    if content_length <= 0:
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_EMPTY,
            message="uploaded object is empty",
        )
    if content_length > settings.object_storage_max_upload_size_bytes:
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_TOO_LARGE,
            message=f"uploaded object exceeds max size {settings.object_storage_max_upload_size_bytes}",
        )

    suffix = Path(object_key).suffix.lower()
    expected_ct = _EXT_TO_CONTENT_TYPE.get(suffix)
    actual_ct = str(head.get("ContentType", "")).lower()
    if expected_ct and not actual_ct.startswith(expected_ct):
        raise BadRequestError(
            code=error_codes.UPLOAD_OBJECT_CONTENT_TYPE_MISMATCH,
            message=f"content type mismatch: expected {expected_ct}, got {actual_ct}",
        )

    stored_etag = str(head.get("ETag", "")).strip() or etag
    original_filename = _metadata_filename(head, object_key)
    existing = db.scalar(
        select(UploadedObject).where(UploadedObject.bucket == bucket, UploadedObject.object_key == object_key)
    )

    with transactional(db):
        if existing is None:
            existing = UploadedObject(
                kb_id=kb.id,
                bucket=bucket,
                object_key=object_key,
                original_filename=original_filename,
                content_type=actual_ct or (expected_ct or "application/octet-stream"),
                size_bytes=content_length,
                etag=stored_etag,
                status=UploadedObjectStatus.uploaded,
                uploader_user_id=uploader_user_id,
            )
            db.add(existing)
            db.flush()
        else:
            existing.kb_id = kb.id
            existing.original_filename = original_filename
            existing.content_type = actual_ct or existing.content_type
            existing.size_bytes = content_length
            existing.etag = stored_etag
            existing.status = UploadedObjectStatus.uploaded
            existing.index_error_message = None
            if uploader_user_id:
                existing.uploader_user_id = uploader_user_id

    return UploadCompletePayload(accepted=True, uploaded_object_id=existing.id)


def list_uploaded_objects(
    *,
    db: Session,
    kb_id: str,
    user_id: str,
    page: int,
    page_size: int,
) -> UploadedObjectListPayload:
    kb = get_knowledge_base_by_id(db, knowledge_base_id=kb_id)
    _assert_kb_read_permission(db, kb=kb, user_id=user_id)

    offset = (page - 1) * page_size
    total = int(
        db.scalar(
            select(func.count())
            .select_from(UploadedObject)
            .where(UploadedObject.kb_id == kb_id, UploadedObject.status != UploadedObjectStatus.deleted)
        )
        or 0
    )
    rows = list(
        db.scalars(
            select(UploadedObject)
            .where(UploadedObject.kb_id == kb_id, UploadedObject.status != UploadedObjectStatus.deleted)
            .order_by(UploadedObject.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return UploadedObjectListPayload(items=[_to_uploaded_object_item(row) for row in rows], page=page, page_size=page_size, total=total)


def get_uploaded_object_detail(*, db: Session, uploaded_object_id: str, user_id: str) -> UploadedObjectItem:
    row = db.get(UploadedObject, uploaded_object_id)
    if row is None or row.status == UploadedObjectStatus.deleted:
        raise NotFoundError(
            code=error_codes.UPLOADED_OBJECT_NOT_FOUND,
            message=f"uploaded object {uploaded_object_id} not found",
        )
    kb = get_knowledge_base_by_id(db, knowledge_base_id=row.kb_id)
    _assert_kb_read_permission(db, kb=kb, user_id=user_id)
    return _to_uploaded_object_item(row)


def delete_uploaded_object(*, db: Session, uploaded_object_id: str, user_id: str) -> None:
    row = db.get(UploadedObject, uploaded_object_id)
    if row is None or row.status == UploadedObjectStatus.deleted:
        raise NotFoundError(
            code=error_codes.UPLOADED_OBJECT_NOT_FOUND,
            message=f"uploaded object {uploaded_object_id} not found",
        )
    kb = get_knowledge_base_by_id(db, knowledge_base_id=row.kb_id)
    _assert_kb_write_permission(db, kb=kb, user_id=user_id)

    _delete_object(bucket=row.bucket, object_key=row.object_key)
    with transactional(db):
        row.status = UploadedObjectStatus.deleted
        row.index_error_message = None


def mark_uploaded_objects_indexed_by_kb(*, db: Session, kb_id: str) -> None:
    rows = list(
        db.scalars(
            select(UploadedObject).where(UploadedObject.kb_id == kb_id, UploadedObject.status == UploadedObjectStatus.uploaded)
        ).all()
    )
    if not rows:
        return
    with transactional(db):
        for row in rows:
            row.status = UploadedObjectStatus.indexed
            row.index_error_message = None


def mark_uploaded_objects_failed_by_kb(*, db: Session, kb_id: str, reason: str | None) -> None:
    rows = list(
        db.scalars(
            select(UploadedObject).where(UploadedObject.kb_id == kb_id, UploadedObject.status == UploadedObjectStatus.uploaded)
        ).all()
    )
    if not rows:
        return
    detail = (reason or "index failed").strip()[:2000]
    with transactional(db):
        for row in rows:
            row.status = UploadedObjectStatus.failed
            row.index_error_message = detail

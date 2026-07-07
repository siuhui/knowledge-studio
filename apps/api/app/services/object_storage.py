"""MinIO / S3-compatible object storage client.

Thin wrapper around boto3 — no database or business logic here.
"""

import re
from pathlib import Path
from typing import Any

import boto3
import structlog
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings
from app.core.errors import AppError, NotFoundError
from app.core.response_codes import ResponseCode

logger = structlog.get_logger(__name__)

_client: Any | None = None
_presign_client: Any | None = None


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for use in S3 object keys.

    Strips directory components, replaces filesystem-hostile and control
    characters with underscores, and truncates to 120 characters.

    Preserves Unicode (CJK, accented Latin, emoji, etc.) — S3 supports UTF-8
    keys natively.
    """
    cleaned = Path(name).name.strip()
    # Denylist approach: only replace characters that cause issues in S3
    # keys or filesystems.  Preserve all Unicode.
    # - Control characters (0x00-0x1F, DEL, C1 controls 0x80-0x9F)
    # - Filesystem-hostile: \\ / : * ? " < > |
    # - # is problematic in presigned POST form fields
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f\\/:*?\"<>|#]+", "_", cleaned)
    return cleaned[:120]


def _get_client() -> Any:
    """Lazy-init the boto3 S3 client (internal endpoint)."""
    global _client
    if _client is None:
        cfg = settings.object_storage
        _client = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key.get_secret_value(),
            region_name=cfg.region,
            config=BotoConfig(signature_version="s3v4"),
        )
        logger.info("object storage client created", endpoint=cfg.endpoint)
    return _client


def _get_presign_client() -> Any:
    """Lazy-init a separate boto3 S3 client for presigned URLs.

    Uses public_endpoint when configured so generated URLs are reachable
    from the browser (e.g. localhost:9000 vs Docker hostname minio:9000).
    """
    global _presign_client
    if _presign_client is None:
        cfg = settings.object_storage
        endpoint = cfg.public_endpoint or cfg.endpoint
        _presign_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key.get_secret_value(),
            region_name=cfg.region,
            config=BotoConfig(signature_version="s3v4"),
        )
        logger.info("presign client created", endpoint=endpoint)
    return _presign_client


class ObjectStorageService:
    """Static methods for MinIO/S3 operations. Lazy client init."""

    @staticmethod
    def generate_presigned_post(
        *, key: str, content_type: str | None = None, max_size_bytes: int | None = None
    ) -> tuple[str, dict[str, str]]:
        """Generate a presigned POST URL + fields for browser direct upload.

        Uses the public-endpoint client so generated URLs are reachable
        from the user's browser, not from inside Docker.
        """
        client = _get_presign_client()
        cfg = settings.object_storage
        max_size = max_size_bytes or cfg.max_upload_size_bytes

        fields: dict[str, str] = {}
        conditions: list[Any] = [["content-length-range", 1, max_size]]

        if content_type is not None:
            fields["Content-Type"] = content_type
            conditions.append({"Content-Type": content_type})

        result = client.generate_presigned_post(
            Bucket=cfg.bucket,
            Key=key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=cfg.presign_expire_seconds,
        )
        return str(result["url"]), dict(result["fields"])

    @staticmethod
    def head_object(*, key: str) -> dict[str, Any]:
        """Return object metadata (ContentLength, ContentType, ETag, Metadata).

        Raises NotFoundError(UPLOAD_OBJECT_NOT_FOUND) if the object doesn't exist.
        Raises AppError(STORAGE_UNAVAILABLE) on other storage errors.
        """
        client = _get_client()
        try:
            return dict(client.head_object(Bucket=settings.object_storage.bucket, Key=key))
        except ClientError as exc:
            http_status = exc.response.get("Error", {}).get("Code", "")
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404 or http_status == "404":
                raise NotFoundError(
                    code=ResponseCode.UPLOAD_OBJECT_NOT_FOUND,
                    message=f"Object not found in storage: {key}",
                )
            raise AppError(
                code=ResponseCode.STORAGE_UNAVAILABLE,
                message="Storage is temporarily unavailable",
                status_code=502,
            )

    @staticmethod
    def get(*, key: str) -> bytes:
        """Download object bytes from storage.

        Raises NotFoundError(UPLOAD_OBJECT_NOT_FOUND) if the object doesn't exist.
        Raises AppError(STORAGE_UNAVAILABLE) on other storage errors.
        """
        client = _get_client()
        try:
            response = client.get_object(Bucket=settings.object_storage.bucket, Key=key)
            raw = response["Body"].read()
            return bytes(raw)
        except ClientError as exc:
            http_status = exc.response.get("Error", {}).get("Code", "")
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404 or http_status == "404":
                raise NotFoundError(
                    code=ResponseCode.UPLOAD_OBJECT_NOT_FOUND,
                    message=f"Object not found in storage: {key}",
                )
            raise AppError(
                code=ResponseCode.STORAGE_UNAVAILABLE,
                message="Storage is temporarily unavailable",
                status_code=502,
            )

    @staticmethod
    def put(*, key: str, body: bytes, content_type: str) -> None:
        """Upload an object from in-memory bytes."""
        client = _get_client()
        client.put_object(
            Bucket=settings.object_storage.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        logger.info("object stored", key=key, size=len(body))

    @staticmethod
    def generate_presigned_get(*, key: str, expires: int = 60) -> str:
        """Generate a presigned GET URL for temporary download access.

        Default expiry is 60 seconds — this is called at download time and the
        browser follows the 302 redirect immediately, so one minute is plenty.
        The presign client is used so the generated URL is reachable from the browser.
        """
        client = _get_presign_client()
        url: str = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.object_storage.bucket, "Key": key},
            ExpiresIn=expires,
        )
        return url

    @staticmethod
    def delete(*, key: str) -> None:
        """Delete a single object. S3 delete_object is idempotent — no error on non-existent keys.

        Raises AppError(STORAGE_UNAVAILABLE) on storage errors.
        """
        client = _get_client()
        try:
            client.delete_object(Bucket=settings.object_storage.bucket, Key=key)
        except ClientError:
            raise AppError(
                code=ResponseCode.STORAGE_UNAVAILABLE,
                message="Storage is temporarily unavailable",
                status_code=502,
            )
        logger.info("object deleted", key=key)

    @staticmethod
    def delete_prefix(*, prefix: str) -> None:
        """Delete all objects under a prefix."""
        client = _get_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.object_storage.bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                client.delete_objects(
                    Bucket=settings.object_storage.bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                )
        logger.info("prefix deleted", prefix=prefix)

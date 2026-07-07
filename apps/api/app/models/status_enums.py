"""Status enums for domain models.

Shared StrEnum values replace hardcoded strings across models,
services, and API routes. Python 3.12+ StrEnum is natively
compatible with pydantic and JSON serialization.
"""

from enum import StrEnum


class DocumentStatus(StrEnum):
    """Content lifecycle — tracks whether full_text was successfully extracted."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class IndexStageStatus(StrEnum):
    """Used by DocumentIndexStatus.{chunk_status, embed_status}."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SourceStatus(StrEnum):
    """Source configuration lifecycle."""

    PENDING = "pending"
    ACTIVE = "active"
    INVALID = "invalid"


class StudioTaskStatus(StrEnum):
    """Studio task lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UploadedObjectStatus(str, enum.Enum):
    uploaded = "uploaded"
    indexed = "indexed"
    failed = "failed"
    deleted = "deleted"


class UploadedObject(Base):
    __tablename__ = "uploaded_object"
    __table_args__ = (UniqueConstraint("bucket", "object_key", name="uk_uploaded_object_bucket_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id"), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[UploadedObjectStatus] = mapped_column(
        Enum(UploadedObjectStatus), nullable=False, default=UploadedObjectStatus.uploaded
    )
    index_error_message: Mapped[str | None] = mapped_column(Text)
    uploader_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

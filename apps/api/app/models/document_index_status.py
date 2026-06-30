"""Document index status — 1:1 extension table for indexing lifecycle.

Document owns the content lifecycle (pending → ready → failed).
DocumentIndexStatus owns the indexing lifecycle (chunk + embed), which
produces searchable derived data.  Separating them keeps Document lean
and avoids conflating business state with pipeline execution state.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentIndexStatus(Base):
    __tablename__ = "document_index_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # pending | running | done | failed
    chunk_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # pending | running | done | failed
    embed_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    embed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    index_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    document = relationship("Document", back_populates="index_status")

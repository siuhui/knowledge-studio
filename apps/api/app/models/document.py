import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source.id", ondelete="SET NULL"), nullable=True
    )
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_format: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf | markdown | text
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # pending | ready | failed   (content lifecycle — does NOT track chunk/embed state)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    doc_version: Mapped[str] = mapped_column(String(32), default="1")
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

    source = relationship("Source", back_populates="documents")
    index_status = relationship(
        "DocumentIndexStatus",
        back_populates="document",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    chunks = relationship(
        "Chunk",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # ── Properties for API serialization (backed by index_status relationship) ──

    @property
    def chunk_status(self) -> str | None:
        if self.index_status is None:
            return None
        return self.index_status.chunk_status

    @property
    def embed_status(self) -> str | None:
        if self.index_status is None:
            return None
        return self.index_status.embed_status

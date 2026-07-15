import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)

    # Document mapping — bridge back to Document.full_text.
    # 0-based half-open: full_text[start_offset:end_offset] == content.
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    # Structure — replaces breadcrumb injection in content.
    # section_path = ["Chapter 2", "Embedding"]; empty list for preamble.
    section_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    heading_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Reserved for parser-specific data (currently empty).
    chunk_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    # Dimension comes from KS_EMBEDDING__DIMENSION config.  If you change the
    # embedding model / dimension after table creation, you must migrate the
    # pgvector column (Alembic) or recreate the table (dev auto_create_tables).
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding.dimension), nullable=True)
    index_version: Mapped[str] = mapped_column(String(32), default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    document = relationship("Document", back_populates="chunks")

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Source(Base):
    __tablename__ = "source"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_base.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="upload"
    )  # upload | url | github
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | inactive | error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="sources")
    documents = relationship("Document", back_populates="source", lazy="selectin")

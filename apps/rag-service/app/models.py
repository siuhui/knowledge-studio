import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class IndexJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class KnowledgeSource(Base):
    __tablename__ = "knowledge_source"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    config_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class IndexJob(Base):
    __tablename__ = "index_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_source.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="incremental")
    status: Mapped[IndexJobStatus] = mapped_column(Enum(IndexJobStatus), nullable=False, default=IndexJobStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text)
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

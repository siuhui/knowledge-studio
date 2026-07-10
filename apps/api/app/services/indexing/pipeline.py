"""Indexing pipeline: chunk → embed.

Two-stage design:
  Stage 1 — chunk_document():  read full_text → chunk → create Chunks (embedding=None)
  Stage 2 — embed_document():  read unembedded chunks → batch embed → write embeddings

Document creation (parse + dedup) lives in services/ingestion/.
"""

import re
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.core.telemetry import observe, update_current_span
from app.models.chunk import Chunk
from app.models.status_enums import IndexStageStatus
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.repositories.document_index_status import DocumentIndexStatusRepository
from app.services.embedding import embedder

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 512  # tokens (approximate: 1 token ≈ 4 chars)
OVERLAP = 50  # tokens


def _estimate_token_count(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text."""
    return len(text) // 4


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Paragraph-aware fixed-window chunking.

    Splits on paragraph boundaries first; if a paragraph exceeds chunk_size,
    falls back to sentence-level splitting.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []

    char_overlap = overlap * 4

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if _estimate_token_count(para) <= chunk_size:
            chunks.append(para)
        else:
            # Paragraph too long, split by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sentence in sentences:
                if _estimate_token_count(current + " " + sentence) <= chunk_size:
                    current = (current + " " + sentence).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sentence
            if current:
                chunks.append(current)

    # Apply overlap: prepend tail of previous chunk to next
    if char_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-char_overlap:]
            overlapped.append(prev_tail + "\n" + chunks[i])
        chunks = overlapped

    return chunks


# ── Stage 1: Chunk ────────────────────────────────────────────────────────────


@observe(name="index.chunk", capture_input=False, capture_output=False)
def chunk_document(db: Session, *, document_id: str) -> int:
    """Read Document.full_text → chunk → create Chunks.

    Idempotent — skips if chunks already exist so re-running the pipeline
    after a partial failure doesn't delete partially-embedded chunks.

    Manages DocumentIndexStatus.chunk_status.
    Returns the number of chunks (existing or newly created).
    """
    update_current_span(input={"document_id": document_id})

    document = DocumentRepository.get_by_id(db, document_id=document_id)
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    existing_count = ChunkRepository.count_by_document(db, document_id=document_id)
    if existing_count > 0:
        logger.info("chunks already exist, skipping", document_id=document_id, chunk_count=existing_count)
        if index_status.chunk_status != IndexStageStatus.DONE:
            index_status.chunk_status = IndexStageStatus.DONE
            index_status.chunk_count = existing_count
            index_status.chunked_at = datetime.now(UTC)
            DocumentIndexStatusRepository.save(db, status=index_status)
        update_current_span(output={"chunk_count": existing_count, "cached": True})
        return existing_count

    index_status.chunk_status = IndexStageStatus.RUNNING
    DocumentIndexStatusRepository.save(db, status=index_status)

    chunk_texts = _chunk_text(document.full_text)
    if not chunk_texts:
        logger.warning("no chunks generated", document_id=document_id)
        chunk_texts = [document.full_text]

    chunk_records = []
    for i, chunk_text in enumerate(chunk_texts):
        chunk = Chunk(
            doc_id=document_id,
            chunk_index=i,
            content=chunk_text,
            token_count=_estimate_token_count(chunk_text),
            embedding=None,
        )
        chunk_records.append(chunk)

    ChunkRepository.save_batch(db, chunks=chunk_records)

    index_status.chunk_status = IndexStageStatus.DONE
    index_status.chunk_count = len(chunk_records)
    index_status.chunked_at = datetime.now(UTC)
    DocumentIndexStatusRepository.save(db, status=index_status)

    logger.info("document chunked", document_id=document_id, chunk_count=len(chunk_records))

    chunk_count = len(chunk_records)
    update_current_span(output={"chunk_count": chunk_count})
    return chunk_count


# ── Stage 2: Embed ──────────────────────────────────────────────────────────────


@observe(name="index.embed", capture_input=False, capture_output=False)
def embed_document(db: Session, *, document_id: str) -> int:
    """Embed unembedded chunks for a document.

    Filters to unembedded only (resume-safe), batches them,
    calls the embedder, and writes embeddings back.

    Manages DocumentIndexStatus.embed_status.
    Returns the number of chunks embedded.
    """
    update_current_span(input={"document_id": document_id})

    chunks = ChunkRepository.list_by_document(db, document_id=document_id)
    index_status = DocumentIndexStatusRepository.get_or_create(db, document_id=document_id)

    unembedded = [c for c in chunks if c.embedding is None]
    if not unembedded:
        logger.info("all chunks already embedded", document_id=document_id)
        if index_status.embed_status != IndexStageStatus.DONE:
            index_status.embed_status = IndexStageStatus.DONE
            index_status.embed_count = len(chunks)
            index_status.embedded_at = datetime.now(UTC)
            index_status.embedding_model = settings.embedding.model
            DocumentIndexStatusRepository.save(db, status=index_status)
        update_current_span(output={"embedded_count": 0, "cached": True})
        return 0

    index_status.embed_status = IndexStageStatus.RUNNING
    index_status.embedding_model = settings.embedding.model
    DocumentIndexStatusRepository.save(db, status=index_status)

    batch_size = settings.embedding.batch_size
    total_embedded = 0

    for i in range(0, len(unembedded), batch_size):
        batch = unembedded[i : i + batch_size]
        texts = [c.content for c in batch]

        embeddings = embedder.embed(texts)

        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding

        total_embedded += len(batch)
        logger.debug("embedding batch", document_id=document_id, batch_start=i, batch_size=len(batch))

    index_status.embed_status = IndexStageStatus.DONE
    index_status.embed_count = len(chunks)
    index_status.embedded_at = datetime.now(UTC)
    DocumentIndexStatusRepository.save(db, status=index_status)

    logger.info("document embedded", document_id=document_id, chunk_count=total_embedded)

    update_current_span(output={"embedded_count": total_embedded, "model": settings.embedding.model})
    return total_embedded


# ── Shared chunk + embed helper ──────────────────────────────────────────────


def _run_chunk_embed(db: Session, *, document_id: str, source_id: str) -> tuple[int, int]:
    """Run chunk and embed stages. Returns (chunk_count, embed_count)."""
    logger.info("indexing started", source_id=source_id, document_id=document_id)

    # Stage 1: Chunk
    try:
        chunk_count = chunk_document(db, document_id=document_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("chunk failed", document_id=document_id)
        _mark_index_failed(document_id=document_id, stage="chunk", error_message=str(e))
        update_current_span(level="ERROR", status_message="Chunk stage failed")
        raise

    logger.info("chunk completed", document_id=document_id, chunk_count=chunk_count)

    # Stage 2: Embed
    try:
        embed_count = embed_document(db, document_id=document_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("embed failed", document_id=document_id)
        _mark_index_failed(document_id=document_id, stage="embed", error_message=str(e))
        update_current_span(level="ERROR", status_message="Embed stage failed")
        raise

    logger.info("embed completed", document_id=document_id, embed_count=embed_count)
    logger.info("index pipeline completed", source_id=source_id, document_id=document_id)
    return chunk_count, embed_count


def _mark_index_failed(*, document_id: str | None, stage: str, error_message: str) -> None:
    """Write failure status to DocumentIndexStatus via an independent session.

    Called after the pipeline main session has been rolled back, so the
    index_status update survives independently of chunk/embed data.
    """
    if document_id is None:
        return

    from app.database import SessionLocal
    from app.models.document_index_status import DocumentIndexStatus

    message = error_message[:500] if error_message else None

    with SessionLocal() as fail_db:
        with fail_db.begin():
            status = fail_db.query(DocumentIndexStatus).filter(DocumentIndexStatus.document_id == document_id).first()
            if status is None:
                status = DocumentIndexStatus(document_id=document_id)
                fail_db.add(status)
            if stage in ("chunk", "embed"):
                setattr(status, f"{stage}_status", IndexStageStatus.FAILED)
            status.error_stage = stage
            status.error_message = message
            logger.info(
                "index status marked as failed",
                document_id=document_id,
                stage=stage,
            )


def run_index_pipeline(source_id: str, kb_id: str, document_id: str) -> None:
    """Background task: chunk → embed for an already-created Document.

    Runs in an independent background thread (FastAPI BackgroundTasks).
    ``@observe`` creates a root span; the decorator degrades to a
    pass-through when telemetry is disabled.
    """
    from app.database import SessionLocal

    @observe(name="index.pipeline", capture_input=False, capture_output=False)
    def _pipeline() -> None:
        db = SessionLocal()
        update_current_span(
            input={"source_id": source_id, "kb_id": kb_id, "document_id": document_id},
        )
        try:
            chunk_count, embed_count = _run_chunk_embed(db, document_id=document_id, source_id=source_id)
            update_current_span(
                output={
                    "document_id": document_id,
                    "chunk_count": chunk_count,
                    "embed_count": embed_count,
                },
            )
        except Exception:
            pass  # _run_chunk_embed already logs + marks failed
        finally:
            db.close()

    _pipeline()
